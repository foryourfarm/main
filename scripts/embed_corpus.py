"""data/<crop>/_chunks.jsonl -> bge-m3 임베딩(Ollama) -> knowledge_chunk 테이블 적재.

로컬 LLM 서버(Ollama, backend/app/core/config.py의 llm_base_url)에서 bge-m3 모델로
임베딩을 받아온다(CLAUDE.md §13 — 로컬 LLM만 사용, 외부 API 아님). LLM은 자연어 변환에만
쓰고 수치 계산에 관여하지 않는다는 원칙과 별개로, 임베딩은 검색용 벡터 생성이라 이 규칙 밖이다.

재실행해도 내용이 같은 청크는 다시 임베딩하지 않는다 — DB에 이미 있는 content와 비교해
신규/변경된 청크만 임베딩·삽입하고, 더 이상 존재하지 않는 청크만 삭제한다(diff 동기화).
**주의**: 비교 기준이 `content`뿐이라 본문은 그대로인데 문서제목·섹션만 바뀐 경우
(= `embed_input`이 달라지는 경우) 재임베딩되지 않는다. 그럴 땐 해당 작물 행을 지우고 다시 돌린다.

사용법 (backend 가상환경으로 실행 — app.* 모듈/의존성이 거기 있음):
    backend/.venv/Scripts/python.exe scripts/embed_corpus.py            # data/ 전체
    backend/.venv/Scripts/python.exe scripts/embed_corpus.py apple      # 특정 작물만

사전 조건:
    - Ollama가 실행 중이고 `ollama pull bge-m3` 완료
    - scripts/chunk_corpus.py를 먼저 실행해 data/<crop>/_chunks.jsonl이 있어야 함
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import httpx  # noqa: E402  (backend venv 의존성 — sys.path 조정 뒤에 import)

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import Crop, KnowledgeChunk  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# data/ 폴더명(영문) -> crop.name(한글, DB.md §3.4 시드값). crop_id는 여기서 하드코딩하지 않고
# 매 실행마다 DB에서 이름으로 조회한다 — 시드 순서가 바뀌어도 스크립트가 안 깨지게.
FOLDER_TO_CROP_NAME = {
    "apple": "사과",
    "pear": "배",
    "cucumber": "오이",
    "potato": "감자",
    "lettuce": "상추",
}

EMBED_DIM = 1024  # bge-m3 dense 차원. knowledge_chunk.embedding = vector(1024)과 반드시 일치(DB.md §3.15)
BATCH_SIZE = 16
EMBED_TIMEOUT_S = 60.0


def validate_embeddings(embeddings: list[list[float]], expected_count: int) -> None:
    """Ollama 응답 검증(공공 API는 아니지만 외부 프로세스 응답이라 진입점에서 방어, CLAUDE.md §12 원칙 준용)."""
    if len(embeddings) != expected_count:
        raise RuntimeError(f"임베딩 응답 개수 불일치: 요청 {expected_count}건, 응답 {len(embeddings)}건")
    for emb in embeddings:
        if len(emb) != EMBED_DIM:
            raise RuntimeError(
                f"임베딩 차원 불일치: {len(emb)} (기대 {EMBED_DIM}) - "
                f"`ollama pull {settings.embedding_model}` 모델이 맞는지 확인"
            )


def embed_batch(client: httpx.Client, texts: list[str]) -> list[list[float]]:
    resp = client.post(
        f"{settings.llm_base_url}/api/embed",
        json={"model": settings.embedding_model, "input": texts},
        timeout=EMBED_TIMEOUT_S,
    )
    resp.raise_for_status()
    embeddings = resp.json().get("embeddings") or []
    validate_embeddings(embeddings, len(texts))
    return embeddings


def embed_input(rec: dict) -> str:
    """임베딩에 넣을 텍스트 = "문서제목 > 섹션" 머리말 + 본문.

    DB에 저장하는 `content`는 본문 그대로 두고 **임베딩 벡터만** 이 텍스트로 만든다.
    청크 본문은 "이 문단이 어느 문서 어느 절인지"를 안 담고 있어서(예: 표 문장 나열),
    질문이 주제어로 들어오면 매칭이 약해진다. 5종 작물 19문항 실측(hit@k)에서 머리말을
    붙이면 4개 청크 설정 전부에서 나아졌다 — @3 0.84->0.95, @5 0.95->1.00(700/1200 기준).
    """
    head = rec["doc_title"] + (f" > {rec['section']}" if rec.get("section") else "")
    return f"{head}\n{rec['content']}"


def load_chunks(crop_dir: Path) -> list[dict]:
    path = crop_dir / "_chunks.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"{path} 없음 - 먼저 scripts/chunk_corpus.py 실행 필요")
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def pick_new_or_changed(records: list[dict], existing_contents: set[str]) -> list[dict]:
    """DB에 이미 있는 content는 그대로 두고, 새로 생겼거나 내용이 바뀐 청크만 골라낸다."""
    return [r for r in records if r["content"] not in existing_contents]


def pick_removed(existing_contents: set[str], current_contents: set[str]) -> set[str]:
    """_chunks.jsonl에서 더 이상 존재하지 않는(삭제되었거나 내용이 바뀐) content."""
    return existing_contents - current_contents


def sync_crop(db, client: httpx.Client, crop_dir: Path, crop_id: int, label: str) -> None:
    records = load_chunks(crop_dir)
    if not records:
        print(f"[{label}] 청크 없음, 건너뜀")
        return

    current_contents = {r["content"] for r in records}
    existing_rows = db.query(KnowledgeChunk).filter(KnowledgeChunk.crop_id == crop_id).all()
    existing_contents = {row.content for row in existing_rows}

    removed = pick_removed(existing_contents, current_contents)
    for row in existing_rows:
        if row.content in removed:
            db.delete(row)

    to_add = pick_new_or_changed(records, existing_contents)
    for i in range(0, len(to_add), BATCH_SIZE):
        batch = to_add[i : i + BATCH_SIZE]
        embeddings = embed_batch(client, [embed_input(r) for r in batch])
        for rec, emb in zip(batch, embeddings, strict=True):
            db.add(
                KnowledgeChunk(
                    source_ref=rec["source_ref"],
                    crop_id=crop_id,
                    content=rec["content"],
                    embedding=emb,
                )
            )
    db.commit()
    unchanged = len(records) - len(to_add)
    print(
        f"[{label}] 총 {len(records)}개 청크 - 신규/변경 {len(to_add)}개 임베딩, "
        f"삭제 {len(removed)}개, 변동없음 {unchanged}개 -> knowledge_chunk(crop_id={crop_id})"
    )


def main() -> None:
    # 기본 대상은 매핑에 있는 작물 폴더뿐이다. data/ 아래 원자재 폴더(raw·soil·aws_daily_cache)까지
    # 훑으면 매번 "건너뜀" 세 줄이 로그를 채워 진짜 건너뜀(청크 없음)과 구분이 안 된다.
    targets = sys.argv[1:] or sorted(FOLDER_TO_CROP_NAME)

    db = SessionLocal()
    try:
        crop_id_by_name = dict(db.query(Crop.name, Crop.id).all())

        with httpx.Client() as client:
            for crop in targets:
                crop_dir = DATA_DIR / crop
                if not crop_dir.is_dir():
                    print(f"건너뜀 (폴더 없음): {crop}")
                    continue

                crop_name_kr = FOLDER_TO_CROP_NAME.get(crop)
                crop_id = crop_id_by_name.get(crop_name_kr) if crop_name_kr else None
                if crop_id is None:
                    print(f"건너뜀 (crop 매핑/DB 시드 없음): {crop}")
                    continue

                sync_crop(db, client, crop_dir, crop_id, crop)
    finally:
        db.close()


if __name__ == "__main__":
    main()
