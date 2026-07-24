"""상담 챗봇 유스케이스: 질문 임베딩 -> pgvector 검색 -> 프롬프트 조립 -> LLM 스트리밍.

라우터엔 로직을 흘리지 않는다(CLAUDE.md §6, §11). LLM/임베딩 실패가 서비스를 막지 않도록
어떤 경우에도 SSE 스트림을 끝맺고, 근거 없거나 생성 실패 시 규칙 기반 문구로 폴백한다(§13, §18-5).

멀티턴은 서버가 저장하지 않고 클라이언트가 history를 실어보내는 무상태 방식이다
(챗봇은 온디맨드·비영속, docs/llm-integration.md §2). 검색은 현재 질문만 임베딩한다 —
생략형 후속질문("그럼 물은?")의 쿼리 재작성은 LLM 호출이 하나 더 붙어 응답 예산을 넘길 수
있어 v1에선 넣지 않는다.
# ponytail: 후속질문 검색 정확도 한계. 필요하면 history로 질문 압축(LLM 1콜) 추가.
"""

import json
from collections.abc import Iterator
from datetime import date

from sqlalchemy.orm import Session

from app.core.config import settings
from app.infra.embedding_client import EmbeddingClient
from app.infra.llm_client import LlmClient, OllamaClient
from app.models import ChatMessage, Crop, KnowledgeChunk, Region, SoilState, User, UserFarm
from app.prompts.chatbot import REFERRAL_TEXT, FarmContext, build_chat_prompt

# 생성 자체가 실패(타임아웃/연결불가/빈 응답)했을 때. 근거 없음(REFERRAL_TEXT)과는 구분한다.
LLM_ERROR_TEXT = "일시적으로 답변을 만들지 못했어요. 잠시 후 다시 시도해 주세요."

SSE_DONE = "data: [DONE]\n\n"

# 요청마다 httpx 호출은 새로 하지만 클라이언트 객체는 재사용(설정만 들고 있음).
_llm = OllamaClient()
_embedder = EmbeddingClient()


def _sse(text: str) -> str:
    """토큰/문구를 SSE data 프레임으로. JSON으로 감싸 개행·특수문자가 프레이밍을 깨지 않게 한다."""
    return f"data: {json.dumps({'token': text}, ensure_ascii=False)}\n\n"


def retrieve_chunks(
    db: Session, query_embedding: list[float], crop_id: int | None = None, top_k: int | None = None
) -> list[str]:
    """질문 임베딩과 코사인 유사도가 높은 knowledge_chunk 내용 top-k. crop_id 주면 그 작물로 한정."""
    k = top_k if top_k is not None else settings.rag_top_k
    q = db.query(KnowledgeChunk.content)
    if crop_id is not None:
        q = q.filter(KnowledgeChunk.crop_id == crop_id)
    q = q.order_by(KnowledgeChunk.embedding.cosine_distance(query_embedding)).limit(k)
    return [content for (content,) in q.all()]


def resolve_crop_name(db: Session, crop_id: int | None) -> str | None:
    """crop_id -> 작물명(프롬프트 [작물] 표시용). 없거나 미지정이면 None -> 모델이 되묻게 된다."""
    if crop_id is None:
        return None
    return db.query(Crop.name).filter(Crop.id == crop_id).scalar()


def load_farm_context(db: Session, user_id: int, farm_id: int | None = None) -> FarmContext | None:
    """로그인 유저의 밭 컨텍스트. farm_id 주면 소유권(user_id 필터) 확인 후 그 밭,
    없으면 유저 밭이 하나뿐일 때만 그 밭. 소유 아님/여러 개 미지정이면 None(밭 컨텍스트 없음)."""
    q = db.query(UserFarm).filter(UserFarm.user_id == user_id)  # 소유권: 항상 요청 유저로 스코프(§11)
    if farm_id is not None:
        farm = q.filter(UserFarm.id == farm_id).first()
    else:
        farms = q.limit(2).all()
        farm = farms[0] if len(farms) == 1 else None
    if farm is None:
        return None
    crop_name = db.query(Crop.name).filter(Crop.id == farm.crop_id).scalar()
    region_name = db.query(Region.name).filter(Region.id == farm.region_id).scalar()
    soil = db.query(SoilState).filter(SoilState.user_farm_id == farm.id).first()
    return FarmContext(
        crop_id=farm.crop_id,
        crop_name=crop_name,
        region_name=region_name,
        days_since_planting=(date.today() - farm.planting_date).days,
        soil_texture=soil.soil_texture if soil else None,
        ph=soil.ph if soil else None,
        ec=soil.ec if soil else None,
        p2o5=soil.p2o5 if soil else None,
        organic_matter=soil.organic_matter if soil else None,
    )


def load_history(db: Session, user_id: int, session_id: str, limit: int) -> list[tuple[str, str]]:
    """(user_id, session_id) 스코프의 최근 대화 limit개(오래된 순). 소유권은 user_id 필터로 강제 —
    남의 session_id를 넣어도 빈 리스트만 돌아온다(§11). id(=삽입순) 역순으로 뽑아 되뒤집는다."""
    rows = (
        db.query(ChatMessage.role, ChatMessage.content)
        .filter(ChatMessage.user_id == user_id, ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    return [(role, content) for role, content in reversed(rows)]


def save_turn(db: Session, user_id: int, session_id: str, question: str, answer: str) -> None:
    """한 턴(user 질문 + assistant 답변)을 저장. 커밋까지. 실패는 호출부에서 흡수(§18-5)."""
    db.add_all(
        [
            ChatMessage(user_id=user_id, session_id=session_id, role="user", content=question),
            ChatMessage(user_id=user_id, session_id=session_id, role="assistant", content=answer),
        ]
    )
    db.commit()


def stream_from_chunks(
    question: str,
    chunks: list[str],
    llm: LlmClient,
    history: list[tuple[str, str]] | None = None,
    crop_name: str | None = None,
    farm: FarmContext | None = None,
    sink: list[str] | None = None,
) -> Iterator[str]:
    """근거 조각이 주어졌을 때의 스트리밍 + 폴백. DB/임베딩과 분리돼 테스트 가능(결정론 경계).
    sink를 주면 실제 생성된 토큰만 담는다(영속화용) — 폴백/거절 문구는 담지 않아 실패한 턴은 저장 안 됨."""
    if not chunks:
        # 검색 결과 자체가 없음 -> 지어내지 말고 전문가/농사로 안내(환각 방지 최우선).
        yield _sse(REFERRAL_TEXT)
        yield SSE_DONE
        return

    prompt = build_chat_prompt(question, chunks, history=history, crop_name=crop_name, farm=farm)
    produced = False
    try:
        for token in llm.generate_stream(prompt):
            if token:
                produced = True
                if sink is not None:
                    sink.append(token)
                yield _sse(token)
    except Exception:
        # 시작 전 실패면 아래 폴백, 도중 실패면 이미 보낸 부분 + [DONE]으로 마무리.
        pass
    if not produced:
        yield _sse(LLM_ERROR_TEXT)
    yield SSE_DONE


def stream_answer(
    db: Session,
    question: str,
    crop_id: int | None = None,
    history: list[tuple[str, str]] | None = None,
    *,
    user: User | None = None,
    farm_id: int | None = None,
    session_id: str | None = None,
    llm: LlmClient | None = None,
    embedder: EmbeddingClient | None = None,
) -> Iterator[str]:
    """엔드포인트가 부르는 진입점. 임베딩+검색 실패도 폴백으로 흡수해 스트림을 반드시 끝맺는다.
    로그인 유저면 밭 컨텍스트를 주입하고, 밭 작물로 crop_id를 자동설정해 되묻기를 건너뛴다.
    로그인+session_id면 DB에서 히스토리를 로드/저장(클라 history 무시), 아니면 클라 history를 쓴다."""
    llm = llm or _llm
    embedder = embedder or _embedder
    persist = user is not None and session_id is not None
    if persist:
        try:
            history = load_history(db, user.id, session_id, settings.chat_history_max_messages)
        except Exception:
            pass  # DB 로드 실패면 넘어온 클라 history로 폴백(챗봇을 막지 않는다, §18-5)
    history = (history or [])[-settings.chat_history_max_messages :]  # 최근 N개만(프롬프트 길이 방어)
    farm = None
    if user is not None:
        try:
            farm = load_farm_context(db, user.id, farm_id)
        except Exception:
            farm = None  # 밭 로드 실패가 챗봇을 막지 않는다(§18-5)
    if farm is not None:
        crop_id = farm.crop_id  # 내 밭 작물로 자동설정 -> 작물 되묻기 제거
    try:
        embedding = embedder.embed_query(question)
        chunks = retrieve_chunks(db, embedding, crop_id)
        crop_name = resolve_crop_name(db, crop_id)
    except Exception:
        yield _sse(LLM_ERROR_TEXT)
        yield SSE_DONE
        return
    sink: list[str] | None = [] if persist else None
    yield from stream_from_chunks(
        question, chunks, llm, history=history, crop_name=crop_name, farm=farm, sink=sink
    )
    if persist and sink:  # 실제 답변이 생성된 턴만 저장(폴백/거절/오류는 sink가 비어 저장 안 됨)
        try:
            save_turn(db, user.id, session_id, question, "".join(sink))
        except Exception:
            pass  # 저장 실패가 이미 흘려보낸 응답을 되돌리지 않는다(§18-5)
