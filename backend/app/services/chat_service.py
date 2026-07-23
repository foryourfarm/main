"""상담 챗봇 유스케이스: 질문 임베딩 -> pgvector 검색 -> 프롬프트 조립 -> LLM 스트리밍.

라우터엔 로직을 흘리지 않는다(CLAUDE.md §6, §11). LLM/임베딩 실패가 서비스를 막지 않도록
어떤 경우에도 SSE 스트림을 끝맺고, 근거 없거나 생성 실패 시 규칙 기반 문구로 폴백한다(§13, §18-5).
"""

import json
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.core.config import settings
from app.infra.embedding_client import EmbeddingClient
from app.infra.llm_client import LlmClient, OllamaClient
from app.models import KnowledgeChunk
from app.prompts.chatbot import REFUSAL_TEXT, build_chat_prompt

# 생성 자체가 실패(타임아웃/연결불가/빈 응답)했을 때. 근거 없음(REFUSAL_TEXT)과는 구분한다.
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


def stream_from_chunks(question: str, chunks: list[str], llm: LlmClient) -> Iterator[str]:
    """근거 조각이 주어졌을 때의 스트리밍 + 폴백. DB/임베딩과 분리돼 테스트 가능(결정론 경계)."""
    if not chunks:
        # 검색 결과 자체가 없음 -> 지어내지 말고 거절(환각 방지 최우선).
        yield _sse(REFUSAL_TEXT)
        yield SSE_DONE
        return

    prompt = build_chat_prompt(question, chunks)
    produced = False
    try:
        for token in llm.generate_stream(prompt):
            if token:
                produced = True
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
    *,
    llm: LlmClient | None = None,
    embedder: EmbeddingClient | None = None,
) -> Iterator[str]:
    """엔드포인트가 부르는 진입점. 임베딩+검색 실패도 폴백으로 흡수해 스트림을 반드시 끝맺는다."""
    llm = llm or _llm
    embedder = embedder or _embedder
    try:
        embedding = embedder.embed_query(question)
        chunks = retrieve_chunks(db, embedding, crop_id)
    except Exception:
        yield _sse(LLM_ERROR_TEXT)
        yield SSE_DONE
        return
    yield from stream_from_chunks(question, chunks, llm)
