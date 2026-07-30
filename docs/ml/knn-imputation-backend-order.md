# 백엔드 KNN 대체 작업 지시서 (Codex 담당)

> ⚠️ **2026-07-30 갱신**: 이 지시서의 §3-3 검증이 실행됐고, 실측으로 정정된 항목이 3개 있다
> (대체 지역 154→140개, 실제 필드 5→3개, `climatology_donor` 테이블 **불필요**).
> **착수 전 `docs/ml/climatology-knn-plan.md`를 먼저 읽을 것 — 충돌 시 그 문서가 우선한다.**
> 백엔드 구현은 여전히 **미착수**다.

> 작성 2026-07-29. 분담: **outcomes/ ML 파이프라인 = Claude(완료), backend/ = Codex(이 문서)**.
> 파일 겹침 없음 — Codex는 `backend/` 와 `scripts/` 만 건드린다. `outcomes/` 는 건드리지 않는다.

## 1. 왜 바꾸나

지금 `backend/app/services/climatology_service.py:load_climatology`는 평년치가 없는 지역
(256개 중 154개)에 대해 **격자상 가장 가까운 1개 지역의 12개월 평년치를 통째로 복사**한다.

문제 3가지.
1. **k=1**. 이웃 하나의 관측 편차·센서 특성이 그대로 전이된다. 그 지역이 산간이거나
   해안이면 대체받는 지역이 함께 왜곡된다.
2. **거리 무가중**. 최근접 선택만 하고 거리에 따른 가중은 없다.
3. **검증 없음**. 이 대체가 시/도 평균이나 다른 방식보다 나은지 측정된 적이 없다.

outcomes/ 쪽에서 같은 문제를 KNN으로 교체하고 측정했다(홀드아웃 정규화 MAE:
종전 최근접5 단순평균 0.6039 → 거리역수 가중 KNN k=5 다변량 0.4300, **28.8% 개선**).
백엔드도 같은 방식으로 맞춘다.

## 2. 제약 (반드시 지킬 것)

- **런타임에 numpy/sklearn 금지**. `backend/app/infra/ml/soil_delta.py` 주석의 원칙과 동일 —
  추론은 사칙연산으로 끝나야 한다. KNN 이웃·가중치는 **오프라인에서 계산해 시드로 적재**하고
  런타임은 그 시드를 읽어 가중평균만 한다.
- **결정론**(CLAUDE.md §2). 동거리 이웃은 `region_id` 작은 쪽. 랜덤 없음.
- **대체 사실 표기 의무**(§18-4). 지금 `substitution_limitation()` 문구는 단일 지역 기준이다 —
  k개 지역을 섞었으면 문구도 그렇게 바뀌어야 한다. "가장 가까운 X(약 N km)"를
  "가까운 X·Y·Z(약 N~M km) 평년치를 거리 가중 평균"으로 갱신한다.
- **결측·장애로 죽지 않기**(§18-5). 시드가 없거나 도너 값이 결측이면 기존 최근접 1개 경로로
  폴백하고, 그것도 없으면 지금처럼 빈 `ClimatologySource`를 돌려준다.
- 스키마 변경은 Alembic 마이그레이션으로만(§10). 런타임 `create_all` 금지.

## 3. 산출물

### 3-1. 시드 생성 스크립트 `scripts/build_climatology_knn_seed.py`

DB(`region_grid`, `weather_climatology`)를 읽어 평년치가 **없는** 각 지역의 도너 목록을 낸다.

- 거리: 기존 `_grid_distance_km`(격자 5km 근사)를 재사용한다. 새로 만들지 말 것 —
  import하거나 동일 공식임을 테스트로 고정한다.
- 도너 후보: 평년치를 12개월 전부 보유한 지역만.
- k: 아래 3-3 검증으로 고른 값. 미리 5로 정하지 말 것.
- 가중치: `1 / max(distance_km, 0.001)`을 도너별로 계산해 **합이 1이 되도록 정규화**한 값을
  시드에 그대로 적재한다(런타임에서 정규화를 반복하지 않는다).
- 출력: `docs/seed/climatology_knn_donors.csv`
  ```
  region_id,donor_region_id,donor_rank,distance_km,weight
  ```
  `donor_rank`는 1부터. `weight` 합은 region_id별로 1.0(±1e-6).

### 3-2. 마이그레이션 + 모델 + 서비스

- 새 테이블 `climatology_donor`(마이그레이션 번호는 현재 최신 다음 것):
  `region_id`(FK region.id), `donor_region_id`(FK region.id), `donor_rank`(int),
  `distance_km`(Numeric), `weight`(Numeric), `source`(str), `fetched_at`(timestamptz).
  인덱스 `(region_id, donor_rank)`. 마스터 데이터이므로 마이그레이션/시드로만 적재하고
  런타임에 수정하지 않는다(§10).
- `backend/app/models/climatology_donor.py` 매핑 추가(SQLAlchemy 2.0 `Mapped`).
- `load_climatology` 수정:
  1. 자기 평년치가 있으면 그대로(변경 없음).
  2. 없으면 `climatology_donor`에서 도너 목록을 읽어 **월별로** 각 수치 필드를 가중평균한다.
     대상 필드: `temp_avg_normal`, `temp_night_min_normal`, `rainfall_normal`,
     `sunlight_normal`, `solar_radiation_normal`.
     - **필드별 독립 처리**: 어떤 도너가 그 필드만 결측이면 그 필드에서만 제외하고 남은
       도너의 가중치를 재정규화한다. 도너 행 전체를 버리지 말 것.
     - 어떤 필드의 모든 도너가 결측이면 그 필드는 `None`(값을 만들어내지 않는다).
     - `0.0`을 결측으로 보지 않도록 `is None`으로만 판정한다 — 기존 `_as_float` 주석에
       기록된 버그(강원 산간 1월 평년기온 0.0℃)를 되살리지 말 것.
  3. `ClimatologySource`에 도너 정보를 담는다. `substituted_from`/`distance_km`는 하위호환을
     위해 1순위 도너 값으로 유지하고, `donors: tuple[tuple[str, float], ...]`(지역명, 거리)를
     추가한다. frozen dataclass이므로 새 필드에는 기본값을 준다.
  4. `substitution_limitation()` 문구를 k개 기준으로 갱신(§2 제약 참조).
- **주의**: 가중평균 결과는 `WeatherClimatology` ORM 인스턴스가 아니다. 지금
  `ClimatologySource.by_month`가 ORM 객체를 담아 호출부가 `clim.temp_avg_normal`로 접근한다.
  ORM 객체를 조립해 세션에 붙이면 안 된다 — 같은 속성을 가진 **비영속 값 객체**(명시적
  frozen dataclass. `SimpleNamespace` 금지)를 만들어 담고 타입힌트를 맞춘다.
  착수 전 `by_month` 사용처를 grep으로 전수 확인해 영향 범위를 보고할 것.

### 3-3. 검증 (필수 산출물)

`scripts/validate_climatology_knn.py` — 평년치를 **보유한** 지역을 홀드아웃해 대체 정확도를
측정한다. outcomes 쪽과 같은 형식으로 비교표를 낸다.

- 후보: `sido_mean`(시/도 평균), `nearest_1`(현행), `knn_spatial_k{1,3,5,7,10}`(거리역수 가중)
- 지표: 필드별 MAE·RMSE + 필드 표준편차로 나눈 정규화 MAE 평균
- 출력: `docs/ml/climatology_knn_validation.json`
- **현행(nearest_1)보다 나쁘면 교체하지 말고 보고할 것.** 개선이 측정되지 않으면 바꿀 근거가 없다.

### 3-4. 테스트

`backend/tests/test_climatology_knn.py` (기존 `test_climatology_service.py` 스타일 —
순수 계산부는 DB 없이, 나머지는 실 DB로).
1. 가중평균이 손계산과 일치(도너 2개, 거리 10km·20km → 가중 2:1).
2. 도너 하나가 특정 필드만 결측일 때 그 필드만 재정규화되고 다른 필드는 두 도너를 다 쓴다.
3. 모든 도너가 결측인 필드는 `None`이고 예외가 나지 않는다.
4. `0.0` 평년기온이 결측으로 떨어지지 않는다(회귀 테스트).
5. 시드가 비어 있으면 기존 최근접 1개 경로로 폴백한다.
6. 같은 입력 2회 호출 결과 동일(결정론).
7. `substitution_limitation()` 문구에 도너 지역명이 **전부** 들어간다.

## 4. 범위 밖 (건드리지 말 것)

- `station_service.py`의 최근접 관측소 매핑. 관측소는 "값"이 아니라 "지점 식별자"를 고르는
  문제라 가중평균이 성립하지 않는다. 관측소에서 가져온 **값**을 섞을지는 별도 결정 사항
  ([확인 필요], 사용자 확인 전 착수 금지).
- `outcomes/` 전체. Claude 담당.
- 적합도 채점 곡선(`suitability_service.py`). 2026-07-27에 이미 개정됨.

## 5. 참고 구현

`outcomes/scripts/ml/imputation.py` — 같은 문제의 오프라인 버전. 특히:
- 거리역수 가중 + 동거리 결정론 tie-break (`_knn_predict`)
- 홀드아웃 CV로 k와 예측인자 구성을 **측정해서** 고르는 방식 (`select_k`)
- 이상치를 자동 치환하지 않고 플래그만 남긴 판단과 근거
  (`build_regional_score.REPLACE_KNN_OUTLIERS` 주석 — 판정된 20건이 전부 실재 가능한 극단값)

## 6. 완료 조건

- [ ] `docs/ml/climatology_knn_validation.json`에 현행 대비 개선이 수치로 있다
- [ ] 테스트 7종 통과
- [ ] 런타임 코드에 numpy/sklearn import 없음
- [ ] UI 노출 한계 문구가 도너 k개를 반영
- [ ] FE 인계 문서 갱신(§3-7): 응답에 도너 정보가 추가되면 계약 문서에 반영
