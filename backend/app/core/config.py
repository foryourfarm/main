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
    # 생성 길이 캡. 200은 한국어 답변(3~5문장 + 목록)엔 부족해 문장 중간에 잘렸다 → 512로 상향.
    # 스트리밍은 read(청크 간격) 타임아웃이라 총 생성시간이 길어도 안전(llm_timeout_s는 총 시간 아님).
    llm_num_predict: int = 512
    # 사실 기반이라 일관성 우선으로 낮게(docs/llm-integration.md §6).
    llm_temperature: float = 0.4

    # 챗봇 RAG 임베딩 — 같은 Ollama 서버, 다른 모델(bge-m3, 1024차원 = knowledge_chunk.embedding과 매칭)
    embedding_model: str = "bge-m3"
    # 질문당 근거로 주입할 문서 조각 수(top-k). 검색 파라미터라 농업 기준값 아님.
    rag_top_k: int = 3
    # 프롬프트에 넣을 이전 대화 최대 메시지 수(최근 것부터). 프롬프트 길이/응답시간 방어용 캡.
    chat_history_max_messages: int = 6

    # 공공데이터 API 키 — 발급 전까지 비워둠(배치/조회 코드에서만 사용)
    weather_api_key: str = ""
    soil_api_key: str = ""

    # 인증 — 분리 토큰 JWT(docs/auth-security.md). 시크릿은 운영에서 반드시 env로 덮어쓴다(§17).
    jwt_secret: str = "dev-only-insecure-secret-change-in-prod-min-32-bytes"
    jwt_algorithm: str = "HS256"
    # 만료시간: access는 짧게(탈취 피해창 최소), refresh는 길게(로그인 유지). 하드코딩 금지라 config로(§4).
    access_token_expire_min: int = 30
    refresh_token_expire_days: int = 14
    # 쿠키 속성 — Secure는 HTTPS에서만 전송되므로 로컬(http localhost)은 False, 운영은 env로 True.
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    # CORS 허용 오리진 — refresh 쿠키가 크로스오리진으로 오가려면 명시 허용 + credentials 필요.
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
