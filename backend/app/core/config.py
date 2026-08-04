import os
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 브라우저가 받아들이는 SameSite 값. 오타(`Lax `, `none;`)는 쿠키가 조용히 안 붙는 원인이 된다.
_VALID_SAMESITE = frozenset({"lax", "strict", "none"})

# 로컬 개발용 JWT 시크릿. **이 값은 리포에 공개돼 있으므로 운영에서 쓰면 인증이 없는 것과 같다** —
# 아는 사람 누구나 임의 user_id로 access 토큰을 서명해 그 계정이 될 수 있다.
# 아래 `_guard_jwt_secret`이 Cloud Run에서 이 값을 거부한다.
_DEV_JWT_SECRET = "dev-only-insecure-secret-change-in-prod-min-32-bytes"

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
    # 생성 런타임 선택: "ollama" | "vllm". `infra.llm_client.make_llm_client()`가 읽는다.
    # 기본은 ollama — vLLM 전환은 이 값 + llm_base_url(:8000)만 바꾸면 되고 재배포가 필요 없다
    # (`--update-env-vars`, docs/vllm.md §5-4). 되돌리기도 같은 방법이라 롤백이 싸다.
    llm_backend: str = "ollama"
    # Qwen3 계열의 "생각 모드"를 끈다. **켜두면 답변이 아예 안 나온다** — L4 vLLM 0.26 실측
    # (2026-08-04): 미지정 시 `content`가 `<think>\nOkay, the user is asking...`로 시작해
    # `max_tokens` 200을 전부 내부 사고(영어)에 쓰고 `finish_reason=length`로 끝났다. 즉 유저는
    # 사고 과정만 보고 답변은 0자다. Ollama에서 `think:false`로 겪은 것과 같은 증상이다.
    # 껐을 때: `completion_tokens=28`, `finish_reason=stop`, 정상 한국어 답변.
    #
    # 모델별로 달라 설정으로 뺀다 — EXAONE엔 무의미하지만 무해하다(모르는 인자는 chat
    # template이 무시한다). Ollama 경로에서는 쓰이지 않는다(그쪽은 `think` 필드가 별도다).
    llm_disable_thinking: bool = True
    llm_model: str = "exaone3.5:7.8b"
    # 8초였으나 실측(Cloud Run + GPU VM, 2026-07-26)상 콜드로드(모델이 VRAM에 없을 때)가
    # exaone3.5:7.8b 67초, bge-m3 18초까지 걸려 첫 요청이 타임아웃으로 죽었다. VM 부팅 시
    # 워밍업 호출(infra/ollama-vm/startup.sh)로 평소엔 이 값까지 안 가지만, 안전망으로 넉넉히 둔다.
    llm_timeout_s: float = 90.0
    # 생성 길이 캡. 200 -> 512로 올렸는데도 목록형 답변(예: "~할 때 주의할 점")이 여전히 잘려
    # 768로 재상향 + 프롬프트에서 목록 대신 문장으로 답하도록 제약 추가(chatbot.py PROMPT_VERSION v5).
    # 스트리밍은 read(청크 간격) 타임아웃이라 총 생성시간이 길어도 안전(llm_timeout_s는 총 시간 아님).
    llm_num_predict: int = 768
    # 입력 컨텍스트 창. **명시하지 않으면 Ollama가 4096으로 로드한다**(모델은 32,768 지원 —
    # `/api/show`의 exaone.context_length. 실측: `/api/ps`의 context_length가 4096으로 뜬다).
    # RAG 최악 케이스(청크 5개 × 1200자 + 대화이력 6개 + 밭정보)를 실측하니 프롬프트만
    # **3,691토큰**이라 4096까지 여유가 405토큰뿐이다 — num_predict(768)를 다 쓰려면 4,459가
    # 필요해 창을 넘고, 그러면 Ollama가 **프롬프트 앞부분부터 버린다.** 우리 프롬프트는 맨 앞이
    # #보안 규칙·#제약조건이라 **안전 규칙이 조용히 날아가는** 방향으로 깨진다(출력이 끊기는
    # 것보다 나쁘다 — 증상이 "이상하게 답함"으로 나와 원인 특정이 어렵다).
    # 8192는 최악 케이스(3,691+768=4,459)에 약 1.8배 여유다. VRAM 증가는 실측상 문제 없었다.
    llm_num_ctx: int = 8192
    # 사실 기반이라 일관성 우선으로 낮게(docs/llm-integration.md §6).
    llm_temperature: float = 0.4

    # 행동추천 다듬기의 **동기 재시도** 타임아웃. 유저가 기다리는 경로라 llm_timeout_s(90초)를
    # 쓸 수 없다 — 넘기면 규칙 문구로 응답하고 다음 조회에 다시 시도한다(advice_service).
    # 정상 상태 실측이 3초 수준이라 8초면 콜드가 아닌 한 충분하다.
    advice_llm_timeout_s: float = 8.0

    # 챗봇 RAG 임베딩 — bge-m3, 1024차원 = knowledge_chunk.embedding과 매칭
    embedding_model: str = "bge-m3"
    # 임베딩 서버 주소. **비워 두면 `llm_base_url`을 쓴다** — 지금까지 둘이 같은 Ollama였고
    # 기본값이 같아야 동작이 바뀌지 않는다(`embedding_base_effective`).
    #
    # **왜 분리하는가**: vLLM은 한 프로세스에 한 모델이라 생성 서버를 vLLM(`:8000`)으로 옮기면
    # 임베딩은 Ollama(`:11434`)에 남아야 한다. 그때 이 값만 다르게 주면 된다(docs/vllm.md §4).
    # Ollama에 임베딩을 남기는 이유는 **재임베딩 회피**다 — `embed_corpus.py`가 적재에 쓴 모델과
    # 같아야 코사인 유사도가 의미를 갖는데(embedding_client docstring), vLLM의 bge-m3는 풀링·
    # 정규화가 다를 수 있어 검증 없이 같은 벡터 공간이라 단정할 수 없다(936청크 재적재 위험).
    embedding_base_url: str = ""
    # 질문당 근거로 주입할 문서 조각 수(top-k). 검색 파라미터라 농업 기준값 아님.
    # 3 -> 5: 5종 작물 19문항으로 hit@k를 실측(scripts/eval_rag_retrieval.py)한 결과
    # @3 0.95 / @5 1.00 / @8 1.00 — 5에서 천장에 닿고 8은 컨텍스트만 늘고 얻는 게 없다.
    rag_top_k: int = 5
    # 프롬프트에 넣을 이전 대화 최대 메시지 수(최근 것부터). 프롬프트 길이/응답시간 방어용 캡.
    chat_history_max_messages: int = 6
    # 화면 복원용으로 돌려주는 지난 대화 최대 메시지 수. 프롬프트 캡(6)과 분리한다 — 모델이
    # 참고할 양과 유저가 다시 읽을 양은 다르다(6개만 복원하면 "기억 못 하는" 화면이 된다).
    chat_history_display_limit: int = 100
    # 대화 목록에 보여줄 스레드 수. 무한 스크롤 대신 최근 것만 — 옛 대화는 검색이 답이지
    # 목록을 길게 늘이는 게 답이 아니다.
    chat_session_list_limit: int = 30
    # 대화 보존 기한(일). **한 시즌 = 1년**이라 365를 기본으로 둔다 — "작년 이맘때 뭘 물었지"가
    # 농업에선 실제로 의미 있는 조회다. 0이면 삭제하지 않는다(기능 끄기).
    # 근거·용량 실측: docs/llm-integration.md §11.2.
    chat_retention_days: int = 365

    # 공공데이터 API 인증키 — API별로 분리한다. data.go.kr은 승인 세트마다 키가 달라
    # (실제로 발급된 값이 서로 다름) 하나로 뭉치면 승인 안 된 API를 잘못된 키로 호출한다.
    # 필드명을 .env 키 이름과 그대로 대응시켜 어떤 키가 어디 쓰이는지 헷갈리지 않게 한다.
    chemical_status_api: str = ""  # 농경지화학성 통계정보 V2
    chemistry_api: str = ""  # 토양검정 화학성 상세정보 V2
    soil_api: str = ""  # 토양도 기반 토양특성 단면정보 V2 (15098809, 심토토성·자갈·경사 3종)
    # 토양도 기반 토양특성 **상세**정보 V3 (15144225) — `soil_api`와 **다른 데이터셋이라 키가
    # 따로다**(승인 세트가 달라 서로의 키로 부르면 실패한다). 이름이 비슷해 헷갈리기 쉬우니
    # 위 단면정보 V2와 나란히 둔다. 27종(배수등급·유효토심·표토토성·**과수적성등급·제약인자** 등)
    # 을 PNU 단위로 주며 **화학성은 없다**(명세서 원문 확인 — nexttodo §토양 데이터원 재조사).
    # 라이선스 제4유형(상업적 이용금지) — 토양검정도 동일하나 착수 전 확인 필요.
    soil_detail_api: str = ""  # [확인 필요] 연동 클라이언트 미구현
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
    # 비료사용처방 **체험** 정보 V2 — 위 fertilizer_api(표준사용량, 작물코드만 입력)와 다른
    # 데이터셋이다. 이건 화학성 값(pH·유기물·유효인산 등)을 입력으로 받아 시비처방을 낸다 —
    # 그래서 토양 결측 밭에는 못 쓰고 화학성 있는 밭 전용이다(nexttodo §미연동 API 3종).
    fertilizer_trial_api: str = ""  # [확인 필요] 연동 클라이언트 미구현
    crop_code_api: str = ""  # 작물코드 목록 정보 — [확인 필요] 연동 클라이언트 미구현

    # 토양변화 shadow 추론 artifact(오프라인 exporter 산출 JSON) 경로.
    # 비어 있으면 미로드 → 모든 예측이 Δ=0 폴백(서비스는 죽지 않음, 가이드 §2.2). 실제 artifact는
    # scripts/ml/export_model.py가 만들며, 백엔드는 읽기만 한다(런타임 재학습 금지, 핸드오프 §3).
    soil_delta_artifact_path: str = ""

    # 인증 — 분리 토큰 JWT(docs/auth-security.md). 시크릿은 운영에서 반드시 env로 덮어쓴다(§17).
    # 기본값은 로컬 전용이고 Cloud Run에서는 `_guard_jwt_secret`이 기동을 막는다.
    jwt_secret: str = _DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    # 만료시간: access는 짧게(탈취 피해창 최소), refresh는 길게(로그인 유지). 하드코딩 금지라 config로(§4).
    access_token_expire_min: int = 30
    refresh_token_expire_days: int = 14
    # 쿠키 속성 — Secure는 HTTPS에서만 전송되므로 로컬(http localhost)은 False, 운영은 env로 True.
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    # CORS 허용 오리진 — refresh 쿠키가 크로스오리진으로 오가려면 명시 허용 + credentials 필요.
    cors_origins: list[str] = ["http://localhost:3000"]

    # 카카오 로그인(docs/auth-security.md §카카오). **비어 있으면 그 엔드포인트만 503으로 꺼진다** —
    # 이메일 로그인은 그대로 동작한다(fail closed, §17).
    #
    # `kakao_rest_api_key`는 비밀이 아니다(FE가 인가 URL을 만들 때 같은 값을 쓴다). 그래서 FE에도
    # `NEXT_PUBLIC_KAKAO_REST_API_KEY`로 같은 값이 들어가는데, **한쪽만 바꾸면 토큰 교환이
    # invalid_client로 죽는다.** 실제로 이 프로젝트에서 env 이름/값 불일치 사고가 세 번 있었다
    # (tests/test_env_example_matches_settings.py 참고) — 바꿀 때 양쪽을 같이 본다.
    kakao_rest_api_key: str = ""
    # 카카오 앱 "보안 → Client Secret"을 켠 경우에만 필요하다. 껐으면 비워둔다 —
    # 빈 값을 보내면 카카오가 invalid_client로 거절하므로 클라이언트가 아예 생략한다.
    kakao_client_secret: str = ""
    # 인가 요청과 토큰 교환에서 **정확히 같아야** 하는 값이고, 카카오 앱에 등록된 것과도 같아야
    # 한다. FE 콜백 주소다(백엔드가 아니다 — access를 메모리에만 두는 정책이라 서버가 리다이렉트를
    # 받으면 토큰을 FE로 넘길 길이 없다).
    kakao_redirect_uri: str = "http://localhost:3000/login/kakao"

    # 운영 작업 엔드포인트(app/api/admin.py) 공유 시크릿. Cloud Scheduler가 X-Admin-Token
    # 헤더로 보낸다. **비워두면 그 엔드포인트가 503으로 꺼진다** — 기본값이 "누구나 통과"가
    # 되면 env를 빠뜨린 배포가 곧 공개 적재 경로가 된다(fail closed, §17).
    admin_task_token: str = ""

    @model_validator(mode="after")
    def _guard_jwt_secret(self) -> "Settings":
        """운영(Cloud Run)에서 공개 기본 시크릿으로 뜨는 것을 막는다 — **fail closed**(§17).

        **왜 조용한 폴백이 위험한가**: 기본값은 이 리포에 그대로 적혀 있다. 그 값으로 서명하면
        누구나 `{"sub": "<임의 user_id>", "type": "access"}`를 직접 만들어 아무 계정이나 될 수
        있다. 비밀번호도 카카오도 필요 없다.

        **왜 이 사고가 실제로 일어날 수 있나**: README §⑤가 적어둔 대로 `--set-env-vars`로
        배포하면 기존 env가 통째로 교체돼 `JWT_SECRET`이 삭제된다. 그때 CORS 차단·토양 API
        401은 **눈에 보이지만** 인증은 조용히 기본값으로 내려앉아 아무 증상도 없다. 이 프로젝트가
        반복해서 겪은 "에러 없이 조용히 거짓이 되는" 실패다.

        `admin_task_token`이 미설정을 "누구나 통과"가 아니라 "기능 꺼짐"으로 보는 것과 같은
        판단이다. 다만 인증은 끌 수 있는 기능이 아니라서 기동 자체를 막는다.

        **로컬·CI는 그대로다.** `K_SERVICE`는 Cloud Run이 항상 주입하는 값이라 그 밖에서는
        이 검사가 돌지 않는다(`log_config.setup_logging`이 쓰는 것과 같은 판별). 새 개발자가
        `.env` 없이도 백엔드를 띄울 수 있다는 성질은 유지된다.

        기동 실패가 서비스 중단이 되지는 않는다 — Cloud Run은 새 리비전이 못 뜨면 트래픽을
        넘기지 않고 기존 리비전이 계속 응답한다. 즉 결과는 "배포 실패"이지 "장애"가 아니다.
        """
        if os.getenv("K_SERVICE") and self.jwt_secret == _DEV_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET이 설정되지 않았다(공개된 개발 기본값 그대로다). "
                "운영에서는 이 값으로 뜨면 누구나 토큰을 위조할 수 있으므로 기동을 막는다. "
                "`gcloud run services update ... --update-env-vars JWT_SECRET=$(openssl rand -hex 32)`로 넣을 것."
            )
        return self

    @model_validator(mode="after")
    def _check_cookie_policy(self) -> "Settings":
        """refresh 쿠키 설정이 브라우저에 거부당하는 조합을 기동 시점에 잡는다.

        **왜 필요한가**: `SameSite=None`은 `Secure` 없이는 브라우저가 쿠키를 **통째로 버린다.**
        그런데 그게 에러로 드러나지 않는다 — 로그인 직후엔 메모리 access 토큰으로 정상 동작하다가
        새로고침하는 순간 `/auth/refresh`가 쿠키를 못 받아 복구 불능이 된다. 실제로 겪은 사고이고
        (FE duckdns.org ↔ BE run.app, 2026-07-26) 증상이 배포 한참 뒤에야 나타나 원인을 찾기
        어려웠다. 크로스사이트 배포에서 한쪽만 켜는 실수가 반복되므로 여기서 막는다(§17).
        """
        samesite = self.cookie_samesite.lower()
        if samesite not in _VALID_SAMESITE:
            raise ValueError(
                f"COOKIE_SAMESITE는 {sorted(_VALID_SAMESITE)} 중 하나여야 한다(받은 값: {self.cookie_samesite!r})"
            )
        if samesite == "none" and not self.cookie_secure:
            raise ValueError(
                "COOKIE_SAMESITE=none은 COOKIE_SECURE=true가 함께 있어야 한다 — "
                "Secure 없는 SameSite=None 쿠키는 브라우저가 버려서 refresh가 항상 401이 된다."
            )
        return self

    @property
    def embedding_base_effective(self) -> str:
        """임베딩 서버 주소. 비어 있으면 생성 서버(`llm_base_url`)를 그대로 쓴다.

        폴백 규칙을 여기 한 곳에만 둔다 — 호출부마다 `or settings.llm_base_url`을 쓰면
        나중에 규칙이 갈린다. `EmbeddingClient`가 이 값을 읽는다.
        """
        return self.embedding_base_url or self.llm_base_url


settings = Settings()
