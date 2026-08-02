from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_REPO_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    """환경변수 설정. 비밀값은 코드/레포에 두지 않고 .env 또는 환경변수로만(CLAUDE.md §17).

    .env는 **리포 루트 한 곳**에만 둔다(`.env.example`도 루트). 두 군데를 읽으면 어느 쪽
    값이 이겼는지 알기 어렵고, 실제로 키를 한쪽에만 넣어 빈 문자열이 되는 사고가 있었다.

    env_file은 절대경로로 준다 — 상대경로 ".env"는 실행 위치(CWD)에 따라 조용히 안 읽힌다
    (backend/에서 실행하면 루트 .env를 못 찾는다).

    키 이름은 대소문자를 구분하지 않고, `KEY = value`처럼 = 앞뒤 공백도 무시된다 —
    실제 .env가 `weather_API = ...` 형식이라 그대로 읽힌다.
    """

    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        extra="ignore",
    )

    # DB — 기본값은 docker-compose.yml의 로컬 Postgres와 동일
    database_url: str = "postgresql+psycopg://foryourfarm:foryourfarm@localhost:5432/foryourfarm"

    # 로컬 LLM (Ollama 개발 / vLLM 서빙 — OpenAI 호환. docs/llm-integration.md)
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "exaone3.5:7.8b"
    # 8초였으나 실측(Cloud Run + GPU VM, 2026-07-26)상 콜드로드(모델이 VRAM에 없을 때)가
    # exaone3.5:7.8b 67초, bge-m3 18초까지 걸려 첫 요청이 타임아웃으로 죽었다. VM 부팅 시
    # 워밍업 호출(infra/ollama-vm/startup.sh)로 평소엔 이 값까지 안 가지만, 안전망으로 넉넉히 둔다.
    llm_timeout_s: float = 90.0
    # 생성 길이 캡. 200 -> 512로 올렸는데도 목록형 답변(예: "~할 때 주의할 점")이 여전히 잘려
    # 768로 재상향 + 프롬프트에서 목록 대신 문장으로 답하도록 제약 추가(chatbot.py PROMPT_VERSION v5).
    # 스트리밍은 read(청크 간격) 타임아웃이라 총 생성시간이 길어도 안전(llm_timeout_s는 총 시간 아님).
    llm_num_predict: int = 768
    # 사실 기반이라 일관성 우선으로 낮게(docs/llm-integration.md §6).
    llm_temperature: float = 0.4

    # 챗봇 RAG 임베딩 — 같은 Ollama 서버, 다른 모델(bge-m3, 1024차원 = knowledge_chunk.embedding과 매칭)
    embedding_model: str = "bge-m3"
    # 질문당 근거로 주입할 문서 조각 수(top-k). 검색 파라미터라 농업 기준값 아님.
    rag_top_k: int = 3
    # 프롬프트에 넣을 이전 대화 최대 메시지 수(최근 것부터). 프롬프트 길이/응답시간 방어용 캡.
    chat_history_max_messages: int = 6

    # 공공데이터 API 인증키 — API별로 분리한다. data.go.kr은 승인 세트마다 키가 달라
    # (실제로 발급된 값이 서로 다름) 하나로 뭉치면 승인 안 된 API를 잘못된 키로 호출한다.
    # 필드명을 .env 키 이름과 그대로 대응시켜 어떤 키가 어디 쓰이는지 헷갈리지 않게 한다.
    chemical_status_api: str = ""  # 농경지화학성 통계정보 V2
    chemistry_api: str = ""  # 토양검정 화학성 상세정보 V2
    soil_api: str = ""  # 토양도 기반 토양특성 단면정보 V2
    weather_api: str = ""  # 농업기상 기본 관측데이터(과거 실측)
    # 농업기상 예비 키. 쿼터가 **엔드포인트별로** 관리돼 특정 엔드포인트만 소진되는 일이
    # 있다(실측: getWeatherYearMonList3는 429인데 getWeatherMonDayList3는 정상).
    # 소진 시 이 키로 재시도한다 — weather_client._fetch_page가 429에서 자동 전환한다.
    weather_api2: str = ""
    weather_observatory_api: str = ""  # 농업기상 관측지점 정보(지점 위경도)
    weather_forecast_api: str = ""  # 기상청 단기예보 조회서비스(단기 탭)
    # 실제 .env 키가 `VWORLD_APIkey`라 필드명이 `vworld_api`면 매칭되지 않아 조용히 빈 값이
    # 됐다(대소문자는 무시되지만 `key` 접미사는 다른 이름이다). .env를 정본으로 두는 방침이라
    # 필드명을 .env에 맞춘다 — 이런 불일치가 다시 생기면 §17 검증 테스트가 잡는다.
    vworld_apikey: str = ""  # VWorld — 주소 → PNU 변환

    # 기상청 API Hub(apihub.kma.go.kr). data.go.kr과 **별개 인증 체계**라 키를 따로 받는다
    # (data.go.kr 키를 넣으면 401). `기상청_API-Guide.md`·`Sunlight-Calculation_API-Guide.md`가
    # 문서화한 엔드포인트 전부가 이 호스트다 — AWS 관측자료(typ02)와 평년값 sfc_norm1.php(typ01)
    # 둘 다. MappingReport.md §2 참고.
    #
    # **필드가 둘로 갈려 있었다.** `weather_apihub_key`(빈 값, kma_station_client가 읽는 쪽)와
    # `weather_data_apikey`(값은 있지만 typ01·typ02 양쪽에서 401)가 같은 자격증명을 가리켰고,
    # 실제 키가 클라이언트가 안 읽는 쪽에 들어가 있었다. 하나로 합치고 두 env 이름을 모두
    # 받아들여 어느 쪽에 넣어도 읽히게 한다 — 이름 불일치로 조용히 빈 값이 되는 것을 막는다(§17).
    weather_apihub_key: str = Field(
        default="",
        validation_alias=AliasChoices("weather_apihub_key", "weather_data_apikey"),
    )
    # 3개월전망(장기 탭)은 RSS라 인증키가 없다(app/infra/public_api/outlook_client.py).

    fertilizer_api: str = ""  # 작물별 비료 표준사용량 처방 정보 — [확인 필요] 연동 클라이언트 미구현
    crop_code_api: str = ""  # 작물코드 목록 정보 — [확인 필요] 연동 클라이언트 미구현

    # 토양변화 shadow 추론 artifact(오프라인 exporter 산출 JSON) 경로.
    # 비어 있으면 미로드 → 모든 예측이 Δ=0 폴백(서비스는 죽지 않음, 가이드 §2.2). 실제 artifact는
    # scripts/ml/export_model.py가 만들며, 백엔드는 읽기만 한다(런타임 재학습 금지, 핸드오프 §3).
    soil_delta_artifact_path: str = ""

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

    # 운영 작업 엔드포인트(app/api/admin.py) 공유 시크릿. Cloud Scheduler가 X-Admin-Token
    # 헤더로 보낸다. **비워두면 그 엔드포인트가 503으로 꺼진다** — 기본값이 "누구나 통과"가
    # 되면 env를 빠뜨린 배포가 곧 공개 적재 경로가 된다(fail closed, §17).
    admin_task_token: str = ""


settings = Settings()
