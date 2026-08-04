"""질문 임베딩 (bge-m3, Ollama /api/embed). 검색용 벡터 생성 — knowledge_chunk와 같은 모델·차원.

keep_alive=-1로 상주시킨다(재로딩 +3.4초, nexttodo.md). scripts/embed_corpus.py가 적재 때 쓴
모델과 반드시 같아야 코사인 유사도가 의미를 가진다.
"""

import httpx

from app.core.config import settings

EMBED_DIM = 1024  # bge-m3 dense. knowledge_chunk.embedding = vector(1024)과 일치해야 함(DB.md §3.15).


class EmbeddingClient:
    def __init__(self, base_url: str | None = None, model: str | None = None, timeout_s: float | None = None) -> None:
        # 생성 서버와 다를 수 있다 — vLLM 전환 시 생성만 :8000으로 옮기고 임베딩은 Ollama에
        # 남긴다(재임베딩 회피, docs/vllm.md §4). 기본값은 llm_base_url과 같아 동작 불변.
        self.base_url = base_url or settings.embedding_base_effective
        self.model = model or settings.embedding_model
        self.timeout_s = timeout_s if timeout_s is not None else settings.llm_timeout_s

    def embed_query(self, text: str) -> list[float]:
        resp = httpx.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": text, "keep_alive": -1},
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        embeddings = resp.json().get("embeddings") or []
        if len(embeddings) != 1 or len(embeddings[0]) != EMBED_DIM:
            raise RuntimeError(
                f"임베딩 응답 이상: {len(embeddings)}건, 차원 {len(embeddings[0]) if embeddings else 0} "
                f"(기대 1건 x {EMBED_DIM}) — `ollama pull {self.model}` 확인"
            )
        return embeddings[0]
