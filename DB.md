# DB.md — 데이터베이스 설계 문서

> DBMS: PostgreSQL (GCP Cloud SQL) · ORM: SQLAlchemy 2.0 · 마이그레이션: Alembic · 접근: FastAPI 경유(클라이언트 직접 접속 없음)
> 게임 규칙은 `PRD.md`, 코딩 규칙은 `CLAUDE.md` 참조.
> **주의:** 게임형 스키마(farm_plot 주차 카운터, action_card, crop_type 등)는 폐기되었다. 이 문서가 현재 유효한 설계다.

---

## 1. 설계 원칙

- **마스터 vs 유저 vs 캐시 분리**:
  - 마스터(시드/사전적재): `region`, `region_grid`, `crop`, `crop_growth_guide`, `soil_change_rule`.
  - 유저 데이터: `users`, `user_farm`, `farm_action_log`.
  - 조회/계산 캐시: `soil_state`, `weather_snapshot`, `weather_climatology`, `weather_outlook`, `suitability_result`, `daily_recommendation`.
- **계산 결정론**: 같은 입력이면 같은 출력(적합도·토양변화·위험판정 전부). LLM은 계산에 관여하지 않는다.
- **실시간 조회 + 캐싱**: 단기 탭은 기상 실시간 조회가 본질. 같은 지역·같은 발표시각은 캐시로 재사용, 갱신 주기를 제한해 rate limit·성능 방어(`PRD.md` §9). 게임 시절의 "실시간 호출 전면 금지"는 폐기.
- **현실 시간 사용**: 유저 농사는 실제 캘린더 날짜(`DATE`)로 진행한다. 게임식 주차 카운터·시간 게이팅 없음.
- **본 프로젝트에 없는 개념**: 게임 요소(승패/RNG/경제/포획/스폰), 지역 이동 그래프, Supabase RLS/Policy/Edge Function(FastAPI가 인가 담당).
- **벡터 검색은 pgvector로**: 상담 챗봇 RAG용 임베딩은 별도 벡터DB가 아니라 PostgreSQL `pgvector` 확장으로 처리(`knowledge_chunk` 테이블). 핵심 예측 기능(적합도/추천)은 RAG를 쓰지 않고 정형 데이터 직접 주입(`PRD.md` §10).

---

## 2. ERD (개념)

```
users 1──N user_farm ──┬──N farm_action_log
                       ├──1 soil_state (현재 추정 토양)
                       └──N daily_recommendation

region 1──1 region_grid
region 1──N weather_snapshot (실황/단기예보 캐시, 작년 실측도 OBS로 재사용)
region 1──N weather_climatology (월별 평년값 캐시)
region 1──N weather_outlook (3개월 장기예보 캐시, 범주형)
crop   1──N crop_growth_guide
(soil_state는 user_farm에 종속 — 지역 기준값을 밭 인스턴스로 복사 후 행위 반영 추정)
(region×crop×생육단계) ─→ suitability_result (장기 적합도 캐시)
soil_change_rule = 행위→지표 변화 계수 (마스터, 토양변화 모델)
knowledge_chunk = 챗봇 RAG 문서 조각 + 임베딩 (pgvector, 독립)
```

- `region`, `region_grid`, `crop`, `crop_growth_guide`, `soil_change_rule`, `knowledge_chunk` = 마스터/사전적재.
- `users`, `user_farm`, `farm_action_log` = 유저 데이터.
- `soil_state`, `weather_snapshot`, `weather_climatology`, `weather_outlook`, `suitability_result`, `daily_recommendation` = 캐시/파생.

---

## 3. 테이블 상세

### 3.1 users (계정)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| email | VARCHAR(255) | UNIQUE, NOT NULL | 로그인 ID |
| password_hash | VARCHAR(255) | NOT NULL | 해시(bcrypt/argon2, 평문 금지) |
| nickname | VARCHAR(50) | NOT NULL | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- Index: `ux_users_email (email)`.

### 3.2 region (지역, 마스터 — 전국 시/군)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | INT | PK | |
| name | VARCHAR(50) | NOT NULL | 시/군명 |
| sido | VARCHAR(30) | NOT NULL | 시/도 |

- 전국 시/군을 시드로 적재(자동완성 소스). Index: `ix_region_name (name)`.

### 3.3 region_grid (기상 격자 매핑, 마스터)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| region_id | INT | PK, FK→region(id) | |
| nx | INT | NOT NULL | 기상청 격자 X |
| ny | INT | NOT NULL | 기상청 격자 Y |

### 3.4 crop (작물, 마스터)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | INT | PK | |
| name | VARCHAR(30) | NOT NULL | 사과/배/오이/감자/상추 |

- 게임식 `crop_type`(TREE/FIELD)·주차 필드 없음.

### 3.5 crop_growth_guide (생육 지침, 마스터·직접 제작) ★핵심★
문헌에서 수작업 추출. 작물×지표×생육단계별 3단계 구간 + 가중치.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| crop_id | INT | FK→crop(id), NOT NULL | |
| growth_stage | VARCHAR(20) | | 생육 단계(발아/생장/개화/결실 등). NULL이면 전 기간 공통 |
| indicator | VARCHAR(30) | NOT NULL | temp_day / temp_night_min / ph / ec / rainfall / sunlight / p2o5 / organic ... |
| optimal_min / optimal_max | NUMERIC | | 적정 구간 |
| allowed_min / allowed_max | NUMERIC | | 허용 구간 (밖 = 위험) |
| weight | NUMERIC | NOT NULL | 이 지표의 작물별 영향도 |

- Constraint: `uq_guide (crop_id, growth_stage, indicator)`.
- **temp_night_min 별도 지표 필수**(야간 최저기온).
- **indicator 문자열 ↔ 소스 컬럼 매핑 규약(C3)**: `indicator` 값은 실제 데이터 소스 컬럼과 1:1로 대응해야 함. 예) `temp_night_min` → `weather_climatology.temp_night_min_normal` / `weather_snapshot.temp_night_min`, `ph`·`ec`·`p2o5`·`organic` → `soil_state.*`. 이 매핑표를 시드와 함께 코드 상수로 관리(오타 시 지표가 조용히 누락되므로 검증 필요).

### 3.6 soil_change_rule (토양 변화 계수, 마스터 — 토양변화 모델) ★신규★
문헌 기반. "어떤 행위가 어떤 지표를 어떻게 바꾸는가"의 계수/공식 파라미터.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | INT | PK | |
| action_type | VARCHAR(30) | NOT NULL | IRRIGATION / FERTILIZE_N / LIMING(석회) ... |
| indicator | VARCHAR(30) | NOT NULL | 영향받는 토양 지표(ph, ec ...) |
| effect_coeff | NUMERIC | NOT NULL | 단위 행위량당 변화량(문헌치) |
| decay_days | INT | | 효과 감쇠 기간(지속성 반영). NULL이면 비감쇠 |
| source_ref | VARCHAR(200) | NOT NULL | 근거 문헌 출처 |

- Constraint: `uq_soil_rule (action_type, indicator)`.
- 계수는 코드 하드코딩 금지 — 이 테이블(시드)로만 관리(`CLAUDE.md`).

### 3.7 user_farm (유저의 밭 = 실제 농사 단위)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| user_id | BIGINT | FK→users(id) ON DELETE CASCADE, NOT NULL | |
| region_id | INT | FK→region(id), NOT NULL | 시/군 — 기상·적합도 단위 |
| bjd_code | CHAR(10) | FK→district(bjd_code) | 읍면동 — 토양 단위(§5). 0014 이전 등록 밭은 NULL |
| crop_id | INT | FK→crop(id), NOT NULL | |
| planting_date | DATE | NOT NULL | 실제 파종/정식일 |
| label | VARCHAR(50) | | 사용자 지정 이름(선택) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- Index: `ix_user_farm_user (user_id)`.
- 한 유저가 여러 밭(지역·작물 조합 자유) 등록 가능.
- 밭의 위치는 (시/군, 읍면동) 한 쌍이 온전한 사실이라 둘 다 저장한다(0014). 설정 화면에서 위치·작물을
  수정하면 `soil_state`를 새 (읍면동, 경지구분) 기준값으로 다시 만든다 — 단 `soil_state_snapshot`
  (실측 이력)·`farm_action_log`(행위 기록)는 유저가 실제로 한 일이라 지우지 않는다.
- **생육 단계**는 저장하지 않고 `planting_date`와 오늘 날짜의 경과일로 파생 계산(§8.3).

### 3.8 farm_action_log (사용자 행동 기록 → 토양변화 입력)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| user_farm_id | BIGINT | FK→user_farm(id) ON DELETE CASCADE, NOT NULL | |
| action_type | VARCHAR(30) | NOT NULL | soil_change_rule.action_type와 대응 |
| amount | NUMERIC | | 행위량(관수량 등, 선택) |
| acted_on | DATE | NOT NULL | 행위 날짜 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- Index: `ix_action_farm (user_farm_id, acted_on)`.

### 3.9 soil_state (밭별 현재 추정 토양 상태)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| user_farm_id | BIGINT | FK→user_farm(id) ON DELETE CASCADE, NOT NULL | |
| soil_texture | VARCHAR(30) | | 토성(기준값, 잘 안 변함) |
| ph / ec / p2o5 / organic_matter | NUMERIC | | 현재 추정값 |
| base_source | VARCHAR(50) | NOT NULL | 기준값 출처(흙토람 등) |
| is_estimated | BOOLEAN | NOT NULL, DEFAULT true | true=행위 반영 추정치(이론), false=실측 기준값 |
| computed_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- Constraint: `uq_soil_state (user_farm_id)` (밭당 현재 상태 1행, 갱신은 upsert).
- 최초=흙토람 기준값(is_estimated=false), 이후 행동 반영 시 추정치로 갱신(§8.2).
- **기준값 단위 = 읍면동**(`PRD.md` §5). 흙토람 토양검정은 읍면동 법정동코드로만 조회되며(시/군 코드는
  "데이터 없음"), 시/군 평균은 편차가 커서 유저 밭과 무관해진다. 등록 작물에 맞는 **경지구분 표본만**
  평균한다(사과·배=과수, 감자·상추=밭, 오이=시설). `base_source`에 조회 단위·표본수를 남겨 재현 가능하게 한다.
- 기상·적합도·ML은 시/군(`region`) 단위 그대로 — 읍면동은 토양에만 쓴다(층 분리 근거는 `PRD.md` §5).

### 3.10 weather_snapshot (기상 실황/예보 캐시)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| region_id | INT | FK→region(id), NOT NULL | |
| kind | VARCHAR(10) | NOT NULL | OBS(실황) / FORECAST(예보) |
| base_at | TIMESTAMPTZ | NOT NULL | 발표/관측 시각 |
| target_date | DATE | NOT NULL | 대상 날짜 |
| temp_avg / temp_night_min / rainfall / sunlight | NUMERIC | | |
| is_imputed | BOOLEAN | NOT NULL, DEFAULT false | 결측 대체 여부 |
| fetched_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 조회 시각 |

- Constraint: `uq_weather (region_id, kind, base_at, target_date)`.
- Index: `ix_weather_region_target (region_id, target_date)`.
- 같은 (지역, kind, 발표시각) 재조회는 캐시 재사용(§PRD 9). 갱신 주기 제한.
- **작년 실측 데이터도 이 테이블 재사용**: `kind='OBS'`, `target_date`를 작년 날짜로. 지역 최초 등록 시 과거관측 API로 최근 1년치를 백필해 캐시(§9). 새 테이블 불필요.

### 3.11 weather_climatology (월별 평년값, 캐시 — 지역 최초 등록 시 확보)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| region_id | INT | FK→region(id), NOT NULL | |
| month | INT | NOT NULL, CHECK 1..12 | |
| temp_avg_normal / temp_night_min_normal / rainfall_normal / sunlight_normal | NUMERIC | | 기상청 평년값 |
| source | VARCHAR(50) | NOT NULL | 출처(기상청 평년값) |
| fetched_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- Constraint: `uq_climatology (region_id, month)`.
- 장기 탭 적합도 계산의 **기준선(baseline)**(§8.1).
- **월 단위**라 생육단계(경과일 기반) 기간과 해상도가 다름 → 단계가 걸치는 월들의 평년값을 일수 가중 평균해 단계 기대값 산출(§8.1 B2).

### 3.12 weather_outlook (3개월 장기예보, 캐시 — 범주형)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| region_id | INT | FK→region(id), NOT NULL | |
| target_month | DATE | NOT NULL | 대상 월(해당 월 1일로 정규화) |
| indicator | VARCHAR(20) | NOT NULL | temp / rainfall |
| category | VARCHAR(10) | NOT NULL, CHECK IN('BELOW','NORMAL','ABOVE') | 평년 대비 전망(최빈 확률 구간) |
| prob_below / prob_normal / prob_above | NUMERIC | | tercile 확률(%) |
| published_at | TIMESTAMPTZ | NOT NULL | 기상청 발표 시각 |
| fetched_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- Constraint: `uq_outlook (region_id, target_month, indicator, published_at)`.
- **평년치(§3.11)에 대한 방향성 보정 신호** — 포인트값이 아니라 확률 범주라 `weather_snapshot`과 구조가 달라 별도 테이블(§8.1).
- **기온·강수만 제공**(KMA 계절전망 특성). 야간최저기온·일조 등 outlook 없는 지표는 평년치 그대로 사용(§8.1 B3).

### 3.13 suitability_result (장기 적합도 baseline 캐시)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| region_id | INT | FK→region(id), NOT NULL | |
| crop_id | INT | FK→crop(id), NOT NULL | |
| growth_stage | VARCHAR(20) | NOT NULL | 생육 단계(또는 시즌 시기 키) |
| score | NUMERIC | NOT NULL, CHECK 0..100 | |
| grade | CHAR(1) | NOT NULL, CHECK IN('S','A','B','C') | |
| breakdown | JSONB | | 지표별 점수/게이지 |
| risk_flags | JSONB | | 위험신호 목록 |
| computed_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- Constraint: `uq_suit (region_id, crop_id, growth_stage)`.
- **이 캐시는 평년치(climatology) 기준 baseline 점수만 저장한다** → (지역,작물,단계) 입력 동일 → 결과 동일, 진짜 결정론적 캐시.
- **장기예보(outlook) 보정은 캐시하지 않고 조회 시점에 얹는다**(§8.1). outlook은 발표마다 바뀌어(시변) 캐시 키로 못 잡으므로, 캐시엔 안정적 baseline만 두고 보정은 read-time에 적용 — 이래야 캐시 결정론이 깨지지 않음(B1).

### 3.14 daily_recommendation (단기 일일 추천 저장)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| user_farm_id | BIGINT | FK→user_farm(id) ON DELETE CASCADE, NOT NULL | |
| target_date | DATE | NOT NULL | 추천 대상일 |
| risk_flags | JSONB | | 그날 위험신호 |
| advice_text | TEXT | | LLM 생성 행동 가이드(폴백 시 규칙 문구) |
| is_llm | BOOLEAN | NOT NULL, DEFAULT true | LLM 생성 여부(폴백이면 false) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- Constraint: `uq_daily (user_farm_id, target_date)`.
- Index: `ix_daily_farm (user_farm_id, target_date)`.
- **생성 시점(B4)**: 스케줄러가 활성 밭 전체를 대상으로 매일 사전생성이 기본. 단, 방금 등록한 밭은 다음 스케줄러 실행 전까지 행이 없으므로 **최초 조회 시 없으면 온디맨드 생성 후 저장**(이후엔 캐시 읽기).

### 3.15 knowledge_chunk (챗봇 RAG 문서 조각, 마스터 · pgvector) [착수 시 구현]
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| source_ref | VARCHAR(200) | NOT NULL | 출처(문서명·URL·페이지 등) |
| crop_id | INT | FK→crop(id) | 작물별 안내책자 조각이면 해당 작물(공통 문서면 NULL) |
| content | TEXT | NOT NULL | 청크 원문 |
| embedding | vector(1024) | NOT NULL | bge-m3 임베딩 (차원 1024) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- **전제**: `CREATE EXTENSION vector;` 필요 → 로컬/운영 Postgres 이미지를 `pgvector/pgvector:pg16`(또는 Cloud SQL의 pgvector 활성화)로 바꿔야 함. 현재 `docker-compose.yml`의 `postgres:16`엔 없음 → 착수 시 교체.
- **1차 코퍼스**: 농사로 작물별 안내책자, 제한 5종(사과·배·오이·감자·상추) 우선 적재(`PRD.md` §4.6). `crop_id`로 작물 필터 후 유사도 검색 가능.
- 검색: 질문 임베딩과 코사인 유사도 상위 K개 조각을 뽑아 프롬프트에 근거로 주입. HNSW/IVFFlat 인덱스는 코퍼스 크기 확정 후 추가.
- **챗봇 전용** — 핵심 예측 기능은 이 테이블을 쓰지 않는다(`PRD.md` §10).

### 3.16 chat_message (상담 챗봇 대화 로그, 런타임 기록)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| user_id | BIGINT | NOT NULL, FK→users(id) ON DELETE CASCADE | 대화 소유 유저 |
| session_id | VARCHAR(64) | NOT NULL | 대화 스레드 키(클라가 만든 uuid4) |
| role | VARCHAR(16) | NOT NULL | 'user' \| 'assistant' |
| content | TEXT | NOT NULL | 발화 원문 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- **런타임 기록 — 시드/마스터 아님**. 로그인 유저가 `session_id`를 주면 서버가 이 테이블에서 히스토리를 로드/저장한다. 게스트는 저장하지 않고 클라이언트가 history를 재전송한다(무상태 경로 유지).
- **소유권(§11·CLAUDE.md §11)**: 히스토리 로드/저장은 항상 `(user_id, session_id)`로 스코프 — 남의 session_id를 넣어도 빈 히스토리만 나온다. 계정 삭제 시 대화도 삭제(FK CASCADE).
- 인덱스: `(user_id, session_id, id)` — 로드가 이 필터 + id(=삽입순) 정렬이라 커버.
- **저장 정책**: 실제 답변이 생성된 턴만 저장(근거 없음 거절·LLM 오류 폴백 문구는 저장 안 함 → 다음 턴 히스토리 오염 방지).

---

## 4. 인덱스 / 제약 요약

- 유니크: users.email, guide(crop,stage,indicator), soil_rule(action,indicator), soil_state(farm), weather(region,kind,base_at,target), climatology(region,month), outlook(region,target_month,indicator,published_at), suit(region,crop,stage), daily(farm,target).
- 조회 인덱스: region(name), user_farm(user), action(farm,date), weather(region,target), daily(farm,target).
- CHECK: score 0..100, grade 화이트리스트, weather.kind ∈ {OBS, FORECAST}, outlook.category ∈ {BELOW, NORMAL, ABOVE}.
- FK: 유저 하위(user_farm/action/soil_state/daily/chat_message)는 `ON DELETE CASCADE`. 마스터 참조는 RESTRICT.

---

## 5. Function / View / Trigger

- **Trigger**: `updated_at` 자동 갱신(users).
- **View**: `v_farm_today` — user_farm + 오늘 날짜 기준 최신 daily_recommendation + soil_state 조인(대시보드 카드용).
- **Function**: 점수·토양변화 계산은 애플리케이션(Python 룰 엔진)에서. DB 함수로 복잡 로직 넣지 않음.

---

## 6. 인가 / 계층 역할

- 클라이언트는 DB 직접 접속 금지, 모든 접근은 FastAPI 경유.
- **api(라우터)**: 요청/응답, 입력 검증(pydantic; 지역·작물 화이트리스트, 날짜 유효성).
- **services**: 트랜잭션 경계, 유스케이스, 소유권 검증(요청 유저 == user_farm.user_id).
- **infra**: SQLAlchemy 접근, 공공 API 클라이언트(기상/토양), LLM 클라이언트, 캐시.
- 행 수준 보안은 서비스 소유권 체크로 구현.

---

## 7. 트랜잭션 / Lock / 캐시 전략

- **읽기 위주**: 대시보드·탭 조회는 캐시 우선.
- **기상 조회**: `weather_snapshot`에 (region, kind, base_at) 캐시. 미스 시에만 외부 API 호출 후 upsert. 갱신 주기(예: 6h) 내 재요청은 캐시 반환.
- **행동 기록 → 토양 재추정**: `farm_action_log` 삽입과 `soil_state` upsert를 한 트랜잭션으로(§8.2).
- **캐시 upsert**: suitability_result / daily_recommendation / soil_state 모두 유니크 키 기준 `ON CONFLICT DO UPDATE` 멱등.
- **외부 API 실패 방어**: 실패 시 마지막 캐시 사용 + "최신 아님" 플래그, 트랜잭션 롤백으로 사용자 요청이 죽지 않게.

---

## 8. 핵심 계산 로직

> 전부 애플리케이션 룰 엔진(결정론). LLM은 계산에 관여하지 않는다.

### 8.1 적합도 점수 (장기, 기존 재사용)
입력: region_id, crop_id, growth_stage.
1. `crop_growth_guide`에서 단계별 지표 (구간, weight) 로드.
2. 실제값(기상) — **[제안] 평년치를 장기예보로 보정, 작년 실측은 점수에 안 섞음**:
   - **baseline(캐시 대상) = 평년치(`weather_climatology`)만으로 산출.** 이게 `suitability_result`에 저장되는 결정론적 값(§3.13, B1).
   - **read-time 보정(캐시 안 함) = baseline + 보정치.** 조회 시점 최신 `weather_outlook`으로 얹는다.
     - **보정치 = P(높음)×(+δ) + P(비슷)×0 + P(낮음)×(−δ)** — tercile 확률 가중.
     - 왜 셋을 동등 평균 안 하나: 평년치=다년 통계, 장기예보=공식 확률예측(신뢰도 있는 조정 신호)이지만 작년 실측=단 1년 샘플(계절 노이즈 큼)이라 동급으로 섞으면 왜곡.
     - 확률 33/33/33이면 보정치 0 → 평년치 그대로.
     - **outlook은 기온·강수만 제공(B3)** → 야간최저기온·일조 등 outlook 없는 지표는 보정 없이 평년치 사용.
     - `δ` 값은 미결정 — 고정 상수로 시작 후 캘리브레이션(`PRD.md` §11).
   - **월→단계 해상도 변환(B2)**: 평년치·outlook은 월 단위. 생육단계 기간이 걸치는 월들의 값을 **일수 가중 평균**해 단계 기대값으로 환산.
   - **작년 실측(`weather_snapshot` OBS)은 점수 계산에 넣지 않고** ①백테스팅(§11) ②유저 리포트 "전망 vs 작년 실제" 병기에만.
   - 토양 = `soil_state`.
3. 지표별 이탈도 점수(적정=100 / 허용=거리 비례 감점 / 위험=큰 감점).
4. 가중 평균 → score, 등급 매핑.
5. breakdown/risk_flags(JSONB) 기록 — 평년치·보정치·최종 기대값을 분해해 기록(정확도 근거 제시, `PRD.md` §11).
6. 결측/이상치는 §8.4로 방어.

### 8.2 토양 변화 추정 (단기, 신규)
입력: `soil_state` 기준값 + 해당 밭의 `farm_action_log` + 기상(강수 등).
1. 각 행동 로그에 대해 `soil_change_rule`에서 (effect_coeff, decay_days) 조회.
2. 경과일에 따른 감쇠 적용: 지표 변화량 = amount × effect_coeff × decay(경과일).
3. 기준값 + Σ변화량 → 현재 추정 지표값. `soil_state`에 upsert(`is_estimated=true`).
4. **이론 추정치임을 항상 표기** — 실측 아님(`PRD.md` §8, §11).

### 8.3 생육 단계 파생
- 경과일 = 오늘 − `user_farm.planting_date`. 경과일 → 작물별 단계 매핑(기준은 미결정 §10). 단계는 저장 안 하고 조회 시 계산.

### 8.4 위험신호 판정
- **단기**: `weather_snapshot`(예보)에서 작물 위험 조건 감지(야간 저온 N일 지속, 과습 등) → daily risk_flags.
- **장기**: 평년치+장기예보+작년 실측(§8.1)에서 시기별 위험 → suitability risk_flags. 예보(단기)와 다른 근거(평년 근사+계절전망)임을 고지.

### 8.5 결측 / 이상치 대체 (Fallback)
- 물리 불가값(pH<0 또는 >14, 음수 강수 등) → 결측 취급.
- 대체: 기상은 인접 기간/평년 보간, 토양은 지역/시도 평균. 대체 시 `is_imputed`/`is_estimated` 플래그.
- 대체 불가 지표는 가중 평균에서 제외 + breakdown에 기록(산출 지속).

---

## 9. 시드 / 마이그레이션

- 전국 시/군 + 격자 매핑 → `region`, `region_grid`.
- 작물별 생육 지침 → `crop`, `crop_growth_guide`.
- 토양 변화 계수(문헌) → `soil_change_rule`.
- 토양/기상(실황·단기예보·평년값·장기예보·작년 실측)은 유저 등록·조회 시점에 API로 확보해 캐시(사전 전량 적재 아님 — 전국 임의 지역이라). 작년 실측은 등록 시 1회 백필.
- 챗봇 RAG: 농사로 작물별 안내책자(5종 우선)를 청킹·임베딩(bge-m3) → `knowledge_chunk` 적재. pgvector 확장 필요(§3.15).
- 마이그레이션은 Alembic으로 관리. 현재 baseline은 `backend/alembic/versions/0001_init_schema.py`(게임 시절 Flyway V1/V2는 폐기 완료). 수동 ALTER 금지.

### 9.1 팀 마이그레이션 워크플로 (로컬 각자 진행)

- **도구**: Alembic. 리비전 파일은 `backend/alembic/versions/`, `alembic revision --autogenerate -m "{설명}"`로 생성.
- **스키마 변경 시**:
  1. `dev`에서 분기한 브랜치에서 모델 수정 → 리비전 생성(기존 리비전 파일 수정 금지 — 이미 merge된 건 불변, 되돌릴 땐 새 리비전 추가).
  2. PR은 항상 `dev` 대상. 리뷰 승인 후 머지.
- **리비전 체인 충돌**: 두 사람이 같은 `down_revision`에서 각자 리비전을 만들면 브랜치 발생 → merge 시 나중 PR이 `down_revision`을 상대 리비전 id로 재작성(rebase)해 단일 체인 유지.
- **로컬 반영**: `dev` pull 후 `alembic upgrade head`로 반영(자동 실행 아님, 앱 기동 전 수동 1회 필요). 반드시 `git pull origin dev` 먼저.
- **주기**: 최소 작업 시작 전 매번 `dev` pull → `alembic upgrade head`. 장기간 안 받으면 merge 시 리비전 체인 어긋남 위험.
- **충돌/실패 시**: 로컬 DB가 깨졌으면(리비전 스킵 등) 로컬 DB만 재생성 후 `alembic upgrade head`로 처음부터 재적용(마스터 데이터 아님, 유저 로컬 개발용이라 삭제 가능). 운영 DB는 별도 담당자만 적용.

---

## 10. 미결정 사항

- 흙토람/기상청 API 반환 스키마 → soil_state/weather_snapshot/weather_climatology/weather_outlook 컬럼 확정.
- **보정 단위 `δ`의 실제 값**(§8.1) — 지표별로 기준편차 비율 등 실제 수치는 캘리브레이션 필요. 결합 구조(평년치+장기예보 보정, 작년은 백테스팅/병기 전용) 자체는 제안 확정.
- 기상청 장기예보(3개월 전망) API 실제 스펙(발표 주기, tercile 확률 형식).
- 토양 변화 계수·감쇠식(문헌 조사 결과) → soil_change_rule 값.
- 지표별 가중치/구간 실제 수치.
- 생육 단계 구분 기준(경과일 → 단계 매핑 테이블 필요 여부).
- 기상 캐시 갱신 주기 확정.
- 챗봇 RAG: 코퍼스 범위, 임베딩 차원(bge-m3=1024 가정), pgvector 인덱스 종류(HNSW/IVFFlat), Postgres 이미지 교체(pgvector).
