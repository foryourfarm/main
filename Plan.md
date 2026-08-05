# Plan.md — 프로그램 시작 계획 (로컬 스크래치, git 추적 안 함)

> 근거: CLAUDE.md, PRD.md, DB.md 읽고 현재 코드 상태(backend/ 실제 파일) 대조해서 작성.
> 미결정 사항(PRD §18, DB §10)은 임의로 정하지 않고 [확인 필요]로 남김.

## 현재 상태 (실제 확인함)

**있음**
- 마스터 엔티티: `Region`, `Crop`(+`CropType`), `ActionCard` + Repository 3종
- Flyway 마이그레이션 V1(init), V2(crop_type/action_card)
- 적합도 계산 도메인: `SuitabilityCalculator`, `SuitabilityResult`, `IndicatorGuide`, `IndicatorInput`, `IndicatorBreakdown`, `DeviationStatus`, `RiskBaseResult`, `SuitabilityGrade` — DB.md §8.1 로직 대응, 순수 도메인(룰 엔진), 테스트 있음
- 카탈로그 조회 API: `CatalogController` → `CatalogQueryService` → `CatalogResponse` (읽기 전용)
- `ApiResponse`(성공/실패 공통 래퍼), `GlobalExceptionHandler`, `SecurityConfig`, `HealthController`
- gradlew 인코딩 버그 수정 완료(커밋 71382e2), 빌드 통과

**없음**
- `frontend/` 디렉터리 자체가 없음 (Next.js 셋업 전)
- `docs/seed/` 없음 → 생육 지침 시드 데이터 없음 (5작물 × 지표 실제 수치)
- User/GameSave/FarmPlot/CultivationLog 엔티티 없음 (인증·세이브·재배기록)
- SoilData/WeatherHistory/RegionGrid 엔티티·시드 없음
- `SuitabilityResult`가 캐시 테이블(`suitability_result`)로 영속화되는지 미확인 — 현재는 도메인 객체로 보임, JPA 캐시 테이블 마이그레이션 필요
- LLM 연동(로컬 모델 인터페이스) 없음
- docker-compose(PostgreSQL) 로컬 기동 여부 — 이전 세션에서 테스트 1개가 DB 연결 실패로 실패했음(인프라 미기동 추정)

## 시작 전 반드시 확인할 것 (PRD §18 / DB §10, 임의 결정 금지)

- [ ] 대상 지역 목록 확정 (몇 개 시/군인지 — region 시드 규모 결정에 필요)
- [ ] 지역↔작물 추천 방향 택1 (지역→작물 vs 작물→지역)
- [ ] 밭작물형 정확한 수확 주 수 (상추4/오이8/감자12 가정 확정)
- [ ] 로컬 LLM 모델/구동 방식
- [ ] 흙토람 API 발급 여부 → 안 되면 토양 데이터 수동 CSV로 대체할지 결정

이 항목들은 아래 순서와 무관하게 **병행해서 사람이 결정**해야 다음 단계(시드 제작, LLM 연동)가 안 막힘.

## 진행 순서 (의존성 순 — 작은 PR 단위, CLAUDE.md §14)

1. **인프라 확인**: `docker-compose up` 으로 PostgreSQL 기동 → `./gradlew test` 10/10 통과 확인. 안 되면 이 다음 뭘 해도 검증 불가.
2. **마스터 엔티티 확장**: `RegionGrid`, `SoilData`, `WeatherHistory`, `CropGrowthGuide` 엔티티 + Repository. 테이블은 V1__init_schema.sql에 이미 존재 확인함 — 새 마이그레이션 불필요, 기존 테이블에 매핑만 (DB.md §3.5~3.9).
3. **시드 데이터 제작**: `docs/seed/`에 작물 5종 생육 지침(농사로 PDF 수작업 추출, CLAUDE.md §12 — 코드에 하드코딩 금지) + 지역 목록 + 토양/작년기상 CSV. 이게 없으면 4번 계산 로직이 실제 데이터로 검증 안 됨.
4. **적합도 계산 API 연결**: 기존 `SuitabilityCalculator`를 실제 리포지토리(soil/weather/guide)에 연결하고 `suitability_result` 캐시 테이블 upsert (DB.md §7 결정론 캐시).
5. **유저/인증**: `User`, `GameSave` 엔티티 + Spring Security 로그인 (CLAUDE.md §11 — DB 직접 노출 금지, 소유권 검증).
6. **밭/주간진행**: `FarmPlot`, `CultivationLog` + `advanceWeek` 유스케이스(단일 트랜잭션, 낙관적 락 — DB.md §7).
7. **행동카드 API**: 기존 `ActionCard` 마스터 활용해 주차별 노출 목록 API (DB.md §3.12 조건 그대로).
8. **LLM 멘토링**: 로컬 모델 인터페이스 추상화 + 프롬프트 템플릿 버전관리 + 폴백 문구 (CLAUDE.md §13, PRD §10 — 계산은 룰 엔진, LLM은 자연어 변환만).
9. **프론트엔드 스캐폴딩**: `frontend/` Next.js App Router 신규 생성 (PRD §4 페이지: login/lobby/지역상세/week/result/재배기록).
10. **프론트-백엔드 연결**: Lobby 탑뷰 → 라디얼 UI → 결과 리포트, 전부 백엔드 API 호출(Next는 BFF/렌더링만, CLAUDE.md §9).

## 왜 이 순서인가

- 시드 데이터(3) 없이는 계산 로직(4)이 진짜 검증 안 됨 — 지금 있는 테스트는 도메인 로직 단위 테스트일 뿐 실제 수치 기반 아님.
- 인증(5)·밭(6) 전에 프론트를 만들면 목업 데이터로 다시 갈아엎어야 함.
- LLM(8)은 스코프가 고정(PRD §10 — 4가지 역할 외 확장 금지)이라 계산/데이터 파이프라인이 먼저 서야 프롬프트 입력이 생김.

## QA 체크 (CLAUDE.md §15, 매 PR 전)

- [ ] 5종 작물 각각 정상 동작
- [ ] 결측/이상치 넣어도 점수 산출 안 죽음
- [ ] 데이터 근사 한계가 UI에 표기됨
- [ ] 로그인/비로그인 접근 제어 동작
- [ ] 색만으로 등급 구분 안 함(라벨 병기)
- [ ] LLM 실패 시 폴백 문구 나옴
