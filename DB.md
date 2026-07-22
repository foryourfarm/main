# DB.md — 데이터베이스 설계 문서

> DBMS: PostgreSQL (GCP Cloud SQL) · ORM: SQLAlchemy 2.0 · 마이그레이션: Alembic · 접근: FastAPI 경유(클라이언트 직접 접속 없음)
> 게임 규칙은 `PRD.md`, 코딩 규칙은 `CLAUDE.md` 참조.
> **주의:** 게임형 스키마(farm_plot 주차 카운터, action_card, crop_type 등)는 폐기되었다. 이 문서가 현재 유효한 설계다.

---

## 1. 설계 원칙

- **마스터 vs 유저 vs 캐시 분리**:
  - 마스터(시드/사전적재): `region`, `region_grid`, `crop`, `crop_growth_guide`, `soil_change_rule`.
  - 유저 데이터: `users`, `user_farm`, `farm_action_log`.
  - 조회/계산 캐시: `soil_state`, `weather_snapshot`, `suitability_result`, `daily_recommendation`.
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
region 1──N weather_snapshot (실황/예보 캐시)
region 1──N soil_state (지역 기준 토양의 유저 farm별 인스턴스)
crop   1──N crop_growth_guide
(region×crop×생육단계) ─→ suitability_result (장기 적합도 캐시)
soil_change_rule = 행위→지표 변화 계수 (마스터, 토양변화 모델)
knowledge_chunk = 챗봇 RAG 문서 조각 + 임베딩 (pgvector, 독립)
```

- `region`, `region_grid`, `crop`, `crop_growth_guide`, `soil_change_rule`, `knowledge_chunk` = 마스터/사전적재.
- `users`, `user_farm`, `farm_action_log` = 유저 데이터.
- `soil_state`, `weather_snapshot`, `suitability_result`, `daily_recommendation` = 캐시/파생.

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
| region_id | INT | FK→region(id), NOT NULL | |
| crop_id | INT | FK→crop(id), NOT NULL | |
| planting_date | DATE | NOT NULL | 실제 파종/정식일 |
| label | VARCHAR(50) | | 사용자 지정 이름(선택) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- Index: `ix_user_farm_user (user_id)`.
- 한 유저가 여러 밭(지역·작물 조합 자유) 등록 가능.
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

### 3.11 suitability_result (장기 적합도 계산 캐시)
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
- 평년 데이터 기반이라 (지역,작물,단계) 입력 동일 → 결과 동일. upsert 캐시.

### 3.12 daily_recommendation (단기 일일 추천 저장)
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

### 3.13 knowledge_chunk (챗봇 RAG 문서 조각, 마스터 · pgvector) [착수 시 구현]
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

---

## 4. 인덱스 / 제약 요약

- 유니크: users.email, guide(crop,stage,indicator), soil_rule(action,indicator), soil_state(farm), weather(region,kind,base_at,target), suit(region,crop,stage), daily(farm,target).
- 조회 인덱스: region(name), user_farm(user), action(farm,date), weather(region,target), daily(farm,target).
- CHECK: score 0..100, grade 화이트리스트, weather.kind ∈ {OBS, FORECAST}.
- FK: 유저 하위(user_farm/action/soil_state/daily)는 `ON DELETE CASCADE`. 마스터 참조는 RESTRICT.

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
2. 실제값: 토양 = `soil_state`(또는 지역 기준값), 기상 = 평년 데이터.
3. 지표별 이탈도 점수(적정=100 / 허용=거리 비례 감점 / 위험=큰 감점).
4. 가중 평균 → score, 등급 매핑.
5. breakdown/risk_flags(JSONB) 기록.
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
- **장기**: 평년 데이터에서 시기별 위험 → suitability risk_flags. 예보 아님(평년 근사)임을 고지.

### 8.5 결측 / 이상치 대체 (Fallback)
- 물리 불가값(pH<0 또는 >14, 음수 강수 등) → 결측 취급.
- 대체: 기상은 인접 기간/평년 보간, 토양은 지역/시도 평균. 대체 시 `is_imputed`/`is_estimated` 플래그.
- 대체 불가 지표는 가중 평균에서 제외 + breakdown에 기록(산출 지속).

---

## 9. 시드 / 마이그레이션

- 전국 시/군 + 격자 매핑 → `region`, `region_grid`.
- 작물별 생육 지침 → `crop`, `crop_growth_guide`.
- 토양 변화 계수(문헌) → `soil_change_rule`.
- 토양/기상은 유저 등록·조회 시점에 API로 확보해 캐시(사전 전량 적재 아님 — 전국 임의 지역이라).
- 스키마 변경은 버전 관리 마이그레이션으로만. **게임 시절 V1/V2는 폐기하고 새 스키마로 재작성**(구현 착수 시 정리).

---

## 10. 미결정 사항

- 흙토람/기상청 API 반환 스키마 → soil_state/weather_snapshot 컬럼 확정.
- 토양 변화 계수·감쇠식(문헌 조사 결과) → soil_change_rule 값.
- 지표별 가중치/구간 실제 수치.
- 생육 단계 구분 기준(경과일 → 단계 매핑 테이블 필요 여부).
- 기상 캐시 갱신 주기 확정.
- 챗봇 RAG: 코퍼스 범위, 임베딩 차원(bge-m3=1024 가정), pgvector 인덱스 종류(HNSW/IVFFlat), Postgres 이미지 교체(pgvector).
