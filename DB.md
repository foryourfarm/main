# DB.md — 데이터베이스 설계 문서

> DBMS: PostgreSQL (GCP Cloud SQL) · ORM: Spring Data JPA · 접근: Spring Boot 경유(클라이언트 직접 접속 없음)
> 게임 규칙은 `PRD.md`, 코딩 규칙은 `CLAUDE.md` 참조.

---

## 1. 설계 원칙

- **읽기 중심 + 사전 적재**: 마스터 데이터(지역, 작물, 생육 지침, 토양, 작년 기상)는 마이그레이션/시드로 미리 적재하고 런타임에 수정하지 않는다. 유저 데이터(계정, 세이브, 재배 기록)만 런타임에 쓰인다.
- **계산 결정론**: 적합도 결과는 (지역, 작물, 주차) 입력이 같으면 항상 같다 → 캐시 테이블로 저장/재사용 가능.
- **본 프로젝트에 없는 개념**: 지역 이동 그래프(`city_connections`), 시간 게이팅(`next_available_at`), 스폰/포획/전설/천장/해금 계산. Supabase의 RLS/Policy/Edge Function도 사용하지 않음(Spring Boot가 인가 담당).
- **경제 시스템은 MVP 범위 아님**: `PRD.md` §16(경제 시스템)은 v2 이후 설계 방향만 정리한 문서고, 지금 스키마엔 `cash_balance`/`economy_log` 같은 테이블·컬럼이 없다.

---

## 2. ERD (개념)

```
users 1──N game_save 1──N farm_plot ──┐
                          │             │ (region_id, crop_id)
                          │      region 1──N soil_data
                          │      region 1──N weather_history
                          │      region 1──1 region_grid
                          │      crop   1──N crop_growth_guide
                          │                                  ▼
                          │                    suitability_result (cache: region×crop×week)
                          └──N cultivation_log

crop 1──N action_card (applicable_crop_type로 매핑, FK 아님)
```

- `region`, `crop`, `crop_growth_guide`, `soil_data`, `weather_history`, `region_grid`, `action_card` = 마스터/사전적재.
- `users`, `game_save`, `farm_plot`, `cultivation_log` = 유저 데이터.
- `suitability_result` = 계산 캐시.

---

## 3. 테이블 상세

### 3.1 users (계정)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| email | VARCHAR(255) | UNIQUE, NOT NULL | 로그인 ID |
| password_hash | VARCHAR(255) | NOT NULL | BCrypt 해시(평문 금지) |
| nickname | VARCHAR(50) | NOT NULL | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- Index: `ux_users_email (email)`.

### 3.2 game_save (세이브/진행 상태)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| user_id | BIGINT | FK→users(id), NOT NULL | |
| current_week | INT | NOT NULL, DEFAULT 1, CHECK ≥1 | 현재 주차 |
| season | VARCHAR(10) | NOT NULL | 파생 표시용(봄/여름/가을/겨울) |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'IN_PROGRESS' | IN_PROGRESS / SEASON_END |
| version | INT | NOT NULL, DEFAULT 0 | 낙관적 락(§7) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- Index: `ix_game_save_user (user_id)`.
- **시간 게이팅 없음**: 주차 진행은 클릭 즉시. `next_available_at` 같은 컬럼은 두지 않는다.

### 3.3 farm_plot (밭 = 지역×작물 관리 슬롯)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| game_save_id | BIGINT | FK→game_save(id), NOT NULL | |
| region_id | INT | FK→region(id), NOT NULL | |
| crop_id | INT | FK→crop(id), NOT NULL | |
| planted_at_week | INT | NOT NULL, DEFAULT 1 | 이 밭이 심어진 시점의 `game_save.current_week` 스냅샷 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- Constraint: `uq_plot (game_save_id, region_id, crop_id)`.
- 잠금/해금 컬럼 없음(밭 전부 오픈).
- **한 지역에 여러 밭 가능**: 유니크 키가 `region_id`만이 아니라 `(region_id, crop_id)` 조합이라, 같은 지역에 작물이 다른 밭이 여러 개 공존할 수 있다(예: 청송에 사과밭·상추밭 동시 존재). 토양(`soil_data`)·기상(`weather_history`)은 `region_id` 하나로 조회해 같은 지역의 모든 밭이 공유하고, `crop_growth_guide`만 작물별로 갈라져 적합도가 밭마다 따로 계산된다.
- **`planted_at_week`은 밭작물형(`crop.crop_type = 'FIELD'`)에만 의미가 있다.** 경과 주수 = `game_save.current_week - planted_at_week`, 이 값이 작물별 수확 주 수(§3.6)에 도달하면 수확 행동카드가 노출된다(`PRD.md` §15). 나무형(`TREE`)은 게임 시작부터 이미 성숙 상태라 이 계산 자체를 쓰지 않는다.

### 3.4 region (지역, 마스터)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | INT | PK | |
| name | VARCHAR(50) | NOT NULL | 시/군명 |
| sido | VARCHAR(30) | NOT NULL | 시/도 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

### 3.5 region_grid (기상 격자 매핑, 마스터)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| region_id | INT | PK, FK→region(id) | |
| nx | INT | NOT NULL | 기상청 격자 X |
| ny | INT | NOT NULL | 기상청 격자 Y |

- 기상 API는 행정구역명이 아닌 격자좌표 기준 → 사전 매핑.

### 3.6 crop (작물, 마스터)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | INT | PK | |
| name | VARCHAR(30) | NOT NULL | 사과/배/오이/감자/상추 |
| crop_type | VARCHAR(10) | NOT NULL, CHECK IN('TREE','FIELD') | TREE=사과·배(이미 성숙 상태로 시작) / FIELD=오이·감자·상추(주차 기반 성장) |
| season_weeks | INT | | 수확까지 걸리는 주 수. **FIELD만 의미 있음**(상추 4 / 오이 8 / 감자 12 — 1개월=4주 가정, 확정 필요 §10). TREE는 NULL. |

### 3.7 crop_growth_guide (생육 지침, 마스터·직접 제작) ★핵심★
농사로 PDF에서 수작업 추출. 작물×지표별 3단계 구간 + 가중치 + 민감도.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| crop_id | INT | FK→crop(id), NOT NULL | |
| indicator | VARCHAR(30) | NOT NULL | temp_day / temp_night_min / ph / ec / rainfall / sunlight / p2o5 / organic ... |
| optimal_min | NUMERIC | | 적정 하한 |
| optimal_max | NUMERIC | | 적정 상한 |
| allowed_min | NUMERIC | | 허용 하한 |
| allowed_max | NUMERIC | | 허용 상한 |
| weight | NUMERIC | NOT NULL | 이 지표의 작물별 영향도(가중치, 매뉴얼에 정량값 없으면 직접 설정) |
| week_from | INT | | 특정 주차 구간에만 적용 시 |
| week_to | INT | | |

- Constraint: `uq_guide (crop_id, indicator, week_from, week_to)`.
- **temp_night_min 별도 지표 필수**(야간 최저기온 — A씨 사례 핵심). 주간 평균과 뭉치지 않는다.
- 허용 범위 밖 = 위험 구간(별도 컬럼 없이 optimal/allowed로 3단계 판정).

### 3.8 soil_data (토양, 사전 적재)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| region_id | INT | FK→region(id), NOT NULL | |
| soil_texture | VARCHAR(30) | | 토성 |
| ph | NUMERIC | | 산도 |
| ec | NUMERIC | | 전기전도도 |
| p2o5 | NUMERIC | | 유효인산 |
| organic_matter | NUMERIC | | 유기물함량 |
| source | VARCHAR(50) | NOT NULL | 출처(흙토람 등) |
| collected_at | TIMESTAMPTZ | NOT NULL | 수집 시각 |
| is_imputed | BOOLEAN | NOT NULL, DEFAULT false | 결측 대체 여부 |

- Constraint: `uq_soil (region_id)` (시/군 단위 평균 1행).

### 3.9 weather_history (작년 기상, 사전 적재 CSV)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| region_id | INT | FK→region(id), NOT NULL | |
| week_no | INT | NOT NULL, CHECK 1..53 | 연중 주차 |
| temp_avg | NUMERIC | | 평균기온 |
| temp_night_min | NUMERIC | | 야간 최저기온 |
| rainfall | NUMERIC | | 강수량 |
| sunlight | NUMERIC | | 일조 |
| is_imputed | BOOLEAN | NOT NULL, DEFAULT false | 결측 대체 여부 |
| collected_at | TIMESTAMPTZ | NOT NULL | |

- Constraint: `uq_weather (region_id, week_no)`.
- Index: `ix_weather_region_week (region_id, week_no)`.
- **정식 설계**: 게임 위험신호는 실시간 예보가 아니라 이 작년 데이터(평년 근사)에서 산출.

### 3.10 suitability_result (적합도 계산 캐시)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| region_id | INT | FK→region(id), NOT NULL | |
| crop_id | INT | FK→crop(id), NOT NULL | |
| week_no | INT | NOT NULL | |
| score | NUMERIC | NOT NULL, CHECK 0..100 | |
| grade | CHAR(1) | NOT NULL, CHECK IN('S','A','B','C') | |
| breakdown | JSONB | | 지표별 점수/게이지 |
| risk_flags | JSONB | | 위험신호 목록 |
| computed_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- Constraint: `uq_suit (region_id, crop_id, week_no)`.
- 입력 동일 → 결과 동일이므로 upsert 캐시.

### 3.11 cultivation_log (재배 기록)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| game_save_id | BIGINT | FK→game_save(id), NOT NULL | |
| region_id | INT | FK→region(id), NOT NULL | |
| crop_id | INT | FK→crop(id), NOT NULL | |
| week_no | INT | NOT NULL | |
| grade | CHAR(1) | NOT NULL | 그 주차 등급 |
| risk_summary | JSONB | | 그 주차 위험 요약 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

- Index: `ix_log_save (game_save_id, week_no)`.

### 3.12 action_card (행동카드 카탈로그, 마스터)
| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | INT | PK | |
| code | VARCHAR(30) | UNIQUE, NOT NULL | 예: WATER, PEST_CONTROL, HARVEST_LETTUCE |
| label | VARCHAR(50) | NOT NULL | 화면 표시명 |
| applicable_crop_type | VARCHAR(10) | CHECK IN('TREE','FIELD') | NULL이면 모든 유형 공통 |
| trigger_week_min | INT | | 경과 주수 하한(해당 밭의 `current_week - planted_at_week`). NULL이면 상시 노출 |
| trigger_week_max | INT | | 경과 주수 상한. NULL이면 하한 이후 계속 노출 |
| description | TEXT | | |

- 이 테이블이 "행동카드 전부 제시" 요구사항의 데이터 원천이다(`PRD.md` §4.3, §15). 특정 주차에 노출할 카드 목록 = `applicable_crop_type`이 NULL 또는 해당 밭의 crop_type과 일치하고, 경과 주수가 `trigger_week_min`/`max` 범위 안(둘 다 NULL이면 무조건 포함)인 행.
- LLM 추천은 이 목록을 애플리케이션이 조회한 뒤, 그중 하나를 추천하도록 프롬프트에 주입(LLM이 카드 존재 여부를 만들어내지 않음).

> **[v2 이후 계획]** 경제 시스템(`PRD.md` §16)을 실제로 만들 때는 `game_save.cash_balance`(누적 수지, NUMERIC) 컬럼과 `economy_log`(game_save_id, week_no, amount, reason, created_at) 테이블을 별도 마이그레이션으로 추가한다. 지금 스키마엔 없음.

---

## 4. 인덱스 / 제약 요약

- 유니크: users.email, farm_plot(save,region,crop), soil(region), weather(region,week), suit(region,crop,week), action_card.code.
- 조회 인덱스: game_save(user), weather(region,week), log(save,week).
- CHECK: score 0..100, grade 화이트리스트, week ≥1, crop.crop_type/action_card.applicable_crop_type ∈ {TREE, FIELD}.
- FK는 모두 `ON DELETE CASCADE`(유저 삭제 시 하위 세이브/기록 정리). 마스터 참조 FK는 RESTRICT.

---

## 5. Function / View / Trigger

- **Trigger**: `updated_at` 자동 갱신 트리거(users, game_save).
- **View**: `v_plot_current_suitability` — farm_plot과 게임 현재 주차 기준 최신 suitability_result 조인(Lobby 등급 표시용).
- **Function**: 점수 계산은 애플리케이션(Java 룰 엔진)에서 수행. DB 함수로 복잡 로직을 넣지 않는다(테스트/버전관리 용이성 위해).

---

## 6. 인가 / 계층 역할 (Supabase RLS 대체)

- 클라이언트는 DB에 직접 접속하지 않는다. 모든 접근은 Spring Boot 경유.
- **Controller**: 요청/응답, 입력 검증(지역·작물 화이트리스트).
- **Service**: 트랜잭션 경계, 유스케이스 조합, 소유권 검증(요청 유저 == game_save.user_id).
- **Repository/Infra**: JPA 접근, 공공 API 클라이언트, 배치.
- 행 수준 보안은 Service의 소유권 체크로 구현(RLS 정책 대신).

---

## 7. 트랜잭션 / Lock 전략

- **읽기 위주**: 대부분 조회는 트랜잭션 없이/읽기 전용.
- **주차 진행**: `advanceWeek(saveId)`는 하나의 트랜잭션 — current_week 증가 + 필요한 suitability 계산/캐시 + cultivation_log 기록.
- **동시성**: 같은 세이브에 대한 중복 "다음 주" 클릭 방지를 위해 game_save 행 갱신 시 낙관적 락(`@Version`) 사용. 충돌 시 재조회 후 무시(멱등 처리).
- **배치 vs 유저 요청**: 마스터 데이터 배치 적재는 별도 시점/트랜잭션. 유저 조회는 커밋된 데이터만 읽음. 마스터는 읽기전용이라 유저 요청과 락 경합 없음.
- **캐시 upsert**: suitability_result는 `ON CONFLICT (region,crop,week) DO UPDATE`로 멱등.

---

## 8. 핵심 계산 로직

> 전부 애플리케이션 룰 엔진(결정론). LLM은 계산에 관여하지 않는다.

### 8.1 적합도 점수 계산 (Suitability)
입력: region_id, crop_id, week_no.
1. `crop_growth_guide`에서 해당 작물·주차의 지표별 (optimal/allowed, weight) 로드.
2. 실제값 로드: 토양 = `soil_data`, 기상 = `weather_history(region, week)` (야간최저기온 포함).
3. 지표별 이탈도 점수:
   - 적정 구간 내 → 100.
   - 허용 구간 내(적정 밖) → 이탈 거리에 비례해 감점(선형/구간 감점).
   - 허용 밖(위험) → 큰 감점(하한 클램프).
4. 가중 평균: `score = Σ(indicatorScore × weight) / Σ(weight)`.
5. 등급 매핑(§PRD 8.2).
6. breakdown/risk_flags(JSONB)로 지표별 결과·위험 기록.
7. **결측/이상치 방어**: 값 없음/범위 밖이면 대체(§8.4) 후 계산, `is_imputed` 반영, 위험도 산출은 지속.

### 8.2 위험신호 판정 (Risk, 평년 기반)
- 해당 주차 및 인접 주차의 작년 데이터에서 작물 위험 조건 감지:
  - 예: `temp_night_min < 작물 허용 하한`이 N주 연속 → "야간 저온 지속" 플래그.
  - 과습(강수 과다), 고온 스트레스 등 지표별 규칙.
- 결과는 risk_flags로. **한계 고지**: 예보 아님, 작년 통상치 기반.

### 8.3 지역↔작물 추천 (택1)
- 방향은 메인 디벨로퍼 판단(둘 중 하나만 구현).
- 지역→작물: 해당 지역에서 5종 각각 현재 주차 기준 score 산출 후 상위 랭킹.
- 작물→지역: 해당 작물로 지정 지역들 score 산출 후 랭킹.
- 실제 산출은 §8.1 재사용(별도 알고리즘 없음 — 5종/지정지역 전수 계산 후 정렬).

### 8.4 결측 / 이상치 대체 (Fallback)
- 이상치: 물리적 불가값(pH<0 또는 >14, 음수 강수 등) → 결측 취급.
- 결측 대체: 기상은 인접 주차 보간 또는 연평균, 토양은 시/도 평균 등. 대체 시 `is_imputed=true`.
- 대체 불가 시 해당 지표를 가중 평균에서 제외하고 그 사실을 breakdown에 기록(점수 산출은 계속).

### 8.5 [v2 이후] 경제 계산 (정보성, 승패 무관) — MVP엔 없음
경제 시스템(`PRD.md` §16)을 만들 때의 계산 방향만 미리 적어둔 것. MVP 스코프가 아니라 지금은 구현하지 않는다.
1. **유지비**: 밭 개수 등 기준 고정값을 매 주차 차감(`reason='UPKEEP'`, 음수).
2. **관광객 방문**: 밭의 `suitability_result.grade`(및 계절)가 조건을 만족하면 고정/조건부 금액을 적립(`reason='TOURISM'`, 양수). **랜덤 없음** — 같은 등급·계절 입력이면 항상 같은 결과(§1 계산 결정론과 동일 원칙).
3. 재료 소모 계산 없음 — 재료는 무제한이라 별도 차감 로직 자체가 존재하지 않는다.

---

## 9. 시드 / 마이그레이션

- `docs/seed/`의 작물별 JSON/YAML(생육 지침) → `crop`, `crop_growth_guide` 적재.
- 지역·격자 매핑 → `region`, `region_grid`.
- 토양·작년 기상 CSV → `soil_data`, `weather_history` (적재 시 §8.4 검증 통과).
- 행동카드 카탈로그(고정 5~10종 수준) → `action_card` 시드로 적재.
- 스키마 변경은 버전 관리되는 마이그레이션으로만(수동 ALTER 금지).

---

## 10. 미결정 사항

- 작물별 시즌 총 주차 수(`crop.season_weeks`, FIELD 작물 — 1개월=4주 가정 확정 필요).
- 흙토람 스키마 확정(soil_data 컬럼 조정 가능).
- 지표별 가중치/구간 실제 수치(생육 지침 제작 결과 반영).
- 지역↔작물 추천 방향 택1.
- 관광객 방문 조건의 구체 임계값(적합도 등급/계절 조합).
- 유지비·관광객 수익 구체 금액.
- 상점 시스템 필요 여부 및 내용 — 필요해지면 별도 테이블 설계.
