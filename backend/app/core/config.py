from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수 설정. 비밀값은 코드/레포에 두지 않고 .env 또는 환경변수로만(CLAUDE.md §17)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DB — 기본값은 docker-compose.yml의 로컬 Postgres와 동일
    database_url: str = "postgresql+psycopg://foryourfarm:foryourfarm@localhost:5432/foryourfarm"

    # 로컬 LLM (Ollama 개발 / vLLM 서빙 — OpenAI 호환. docs/llm-integration.md)
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "exaone3.5:7.8b"
    llm_timeout_s: float = 8.0

    # 챗봇 RAG 임베딩 — 같은 Ollama 서버, 다른 모델(bge-m3, 1024차원 = knowledge_chunk.embedding과 매칭)
    embedding_model: str = "bge-m3"

    # 공공데이터 API 키 — 발급 전까지 비워둠(배치/조회 코드에서만 사용)
    weather_api_key: str = ""
    soil_api_key: str = ""


settings = Settings()
