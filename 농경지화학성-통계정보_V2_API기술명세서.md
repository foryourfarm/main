
## 1. 개요
- **Base URL**: `https://apis.data.go.kr/1390802/SoilEnviron/SoilExamStat/V2`
- **API 유형**: REST (GET)
- **데이터포맷**: XML (포털 예시는 JSON 모델로도 제공됨)
- **인증방식**: 쿼리 파라미터 `serviceKey` (공공데이터포털 발급 인증키)
- **공통 요청 파라미터**

| 이름 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| serviceKey | query | string | Y | 공공데이터포털에서 받은 인증키 |
| STDG_CD | query | string | Y | 법정동코드(10자리) |

- **공통 응답 코드**

| 코드 | 설명 |
|---|---|
| 101 | 서비스키 인증 실패 |
| 200 | 성공 |
| 201 | 요청변수 형식이 일치하지 않은 경우 |
| 202 | 요청변수로 0 이하 음수 값은 허용하지 않음 |
| 203 | 요청변수 값으로 null을 허용하지 않음 |
| 204 | 필수 요청변수 미입력 |
| 301 | 요청 데이터 없음 |
| 400 | 요청 페이지 형식 오류 |
| 404 | 요청 페이지가 존재 않음 |
| 500 | 내부 서버 문제 발생 |
| 600 | 프로그램 오류 |
| 999 | 기타 알수 없는 오류 |
- 응답의 항목 구분: 필수(1), 옵션(0)

---

## 2. GET /getFarmExamOmInfo — 농경지화학성_유기물 통계 정보 조회
설명: 법정동코드(10자리)로 유기물 통계 정보 조회

**호출코드**: GET [https://apis.data.go.kr/1390802/SoilEnviron/SoilExamStat/V2/getFarmExamOmInfo?serviceKey=발급받은인증키&STDG_CD=법정동코드10자리]
**요청 파라미터**

| 이름 | 타입 | 필수 | 설명 |
|---|---|---|---|
| serviceKey | string | Y | 인증키 |
| STDG_CD | string | Y | 법정동코드 |

**응답 결과 코드**: 공통 응답 코드 표와 동일 (101/200/201/202/203/204/301/400/404/500/600/999)

**응답 Body 구조 (item)**
- `stdg_Cd`, `bjd_Nm`
- `om_Rfld1_Area` ~ `om_Rfld6_Area` (string)
- `om_Pfld1_Area` ~ `om_Pfld6_Area` (string)
- `om_Fachs1_Area` ~ `om_Fachs6_Area` (string)
- `om_Fruit1_Area` ~ `om_Fruit6_Area` (string)
- header: `result_Code`(0), `result_Msg`(string)

| 항목명(영문)        | 항목명(국문)                  | 항목<br><br>크기 | 항목<br><br>구분 | 샘플<br><br>데이터 | 항목설명                                       |
| -------------- | ------------------------ | ------------ | ------------ | ------------- | ------------------------------------------ |
| result_Code    | 결과코드                     | 3            | 1            | 200           | 결과코드                                       |
| result_Msg     | 결과메세지                    | 50           | 1            | OK            | 결과메시지                                      |
| stdg_Cd        | 법정동코드                    | 10           | 1            | 5279000000    | 시도,시군구,읍면동 법정동코드 값<br><br>* 행안부, 행정표준코드 참조 |
| bjd_Nm         | 법정동명                     | 50           | 1            | 전라북도 고창군      | 법정동명                                       |
| om_Rfld1_Area  | 유기물 논10이하_면적             | 8            | 1            | 375           | 유기물 논10이하_면적(ha)                           |
| om_Rfld2_Area  | 유기물 논11~20이하_면적          | 8            | 1            | 5230          | 유기물 논11~20이하_면적<br><br>(ha)                |
| om_Rfld3_Area  | 유기물 논21~30이하_면적          | 8            | 1            | 3768          | 유기물 논21~30이하_면적<br><br>(ha)                |
| om_Rfld4_Area  | 유기물 논31~40이하_면적          | 8            | 1            | 813           | 유기물 논31~40이하_면적<br><br>(ha)                |
| om_Rfld5_Area  | 유기물 논41~50이하_면적          | 8            | 1            | 171           | 유기물 논41~50이하_면적<br><br>(ha)                |
| om_Rfld6_Area  | 유기물 논51이상_면적             | 8            | 1            | 14            | 유기물 논51이상_면적(ha)                           |
| om_Pfld1_Area  | 유기물 밭10이하_면적             | 8            | 1            | 1713          | 유기물 밭10이하_면적(ha)                           |
| om_Pfld2_Area  | 유기물 밭11~20이하_면적          | 8            | 1            | 5344          | 유기물 밭11~20이하_면적<br><br>(ha)                |
| om_Pfld3_Area  | 유기물 밭21~30이하_면적          | 8            | 1            | 2745          | 유기물 밭21~30이하_면적<br><br>(ha)                |
| om_Pfld4_Area  | 유기물 밭31~40이하_면적          | 8            | 1            | 551           | 유기물 밭31~40이하_면적<br><br>(ha)                |
| om_Pfld5_Area  | 유기물 밭41~50이하_면적          | 8            | 1            | 127           | 유기물 밭41~50이하_면적<br><br>(ha)                |
| om_Pfld6_Area  | 유기물 밭51이상_면적             | 8            | 1            | 117           | 유기물 밭51이상_면적(ha)                           |
| om_Fachs1_Area | 유기물 시설10이하_면적            | 8            | 1            | 200           | 유기물 시설10이하_면적(ha)                          |
| om_Fachs2_Area | 유기물 시설11~20이하_<br><br>면적 | 8            | 1            | 1246          | 유기물 시설11~20이하_면적<br><br>(ha)               |
| om_Fachs3_Area | 유기물 시설21~30이하_<br><br>면적 | 8            | 1            | 550           | 유기물 시설21~30이하_면적<br><br>(ha)               |
| om_Fachs4_Area | 유기물 시설31~40이하_<br><br>면적 | 8            | 1            | 133           | 유기물 시설31~40이하_면적<br><br>(ha)               |
| om_Fachs5_Area | 유기물 시설41~50이하_<br><br>면적 | 8            | 1            | 39            | 유기물 시설41~50이하_면적<br><br>(ha)               |
| om_Fachs6_Area | 유기물 시설51이상_면적            | 8            | 1            | 10            | 유기물 시설51이상_면적(ha)                          |
| om_Fruit1_Area | 유기물 과수10이하_면적            | 8            | 1            | 50            | 유기물 과수10이하_면적(ha)                          |
| om_Fruit2_Area | 유기물 과수11~20이하_<br><br>면적 | 8            | 1            | 111           | 유기물 과수11~20이하_면적<br><br>(ha)               |
| om_Fruit3_Area | 유기물 과수21~30이하_<br><br>면적 | 8            | 1            | 117           | 유기물 과수21~30이하_면적<br><br>(ha)               |
| om_Fruit4_Area | 유기물 과수31~40이하_<br><br>면적 | 8            | 1            | 55            | 유기물 과수31~40이하_면적<br><br>(ha)               |
| om_Fruit5_Area | 유기물 과수41~50이하_<br><br>면적 | 8            | 1            | 27            | 유기물 과수41~50이하_면적<br><br>(ha)               |
| om_Fruit6_Area | 유기물 과수51이상_면적            | 8            | 1            | 18            | 유기물 과수51이상_면적(ha)                          |


---

## 3. GET /getFarmExamApInfo — 농경지화학성_유효인산 통계 정보 조회
설명: 법정동코드(10자리)로 유효인산 통계 정보 조회

**호출코드**: GET [https://apis.data.go.kr/1390802/SoilEnviron/SoilExamStat/V2/getFarmExamApInfo?serviceKey=발급받은인증키&STDG_CD=법정동코드10자리]
**요청 파라미터**: serviceKey(string, Y), STDG_CD(string, Y) — 상동

**응답 결과 코드**: 공통 응답 코드 표와 동일

**응답 Body 구조 (item)**
- `stdg_Cd`, `bjd_Nm`
- `vldpha_Rfld1_Area` ~ `vldpha_Rfld6_Area` (number)
- `vldpha_Pfld1_Area` ~ `vldpha_Pfld6_Area` (number)
- `vldpha_Fachs1_Area` ~ `vldpha_Fachs6_Area` (number)
- `vldpha_Fruit1_Area` ~ `vldpha_Fruit6_Area` (number)
- header: `result_Code`(0), `result_Msg`(string)

| 항목명(영문)            | 항목명(국문)                       | 항목<br><br>크기 | 항목<br><br>구분 | 샘플<br><br>데이터 | 항목설명                                       |
| ------------------ | ----------------------------- | ------------ | ------------ | ------------- | ------------------------------------------ |
| result_Code        | 결과코드                          | 3            | 1            | 200           | 결과코드                                       |
| result_Msg         | 결과메세지                         | 50           | 1            | OK            | 결과메시지                                      |
| stdg_Cd            | 법정동코드                         | 10           | 1            | 5279000000    | 시도,시군구,읍면동 법정동코드 값<br><br>* 행안부, 행정표준코드 참조 |
| bjd_Nm             | 법정동명                          | 50           | 1            | 전라북도 고창군      | 법정동명                                       |
| vldpha_Rfld1_Area  | 유효인산 논50이하_면적                 | 8            | 1            | 4722          | 유효인산 논50이하_면적(ha)                          |
| vldpha_Rfld2_Area  | 유효인산 논51~100이하_<br><br>면적     | 8            | 1            | 2884          | 유효인산 논51~100이하_<br><br>면적(ha)              |
| vldpha_Rfld3_Area  | 유효인산 논101~150이하<br><br>_면적    | 8            | 1            | 1224          | 유효인산 논101~150이하<br><br>_면적(ha)             |
| vldpha_Rfld4_Area  | 유효인산 논151~200이하<br><br>_면적    | 8            | 1            | 437           | 유효인산 논151~200이하<br><br>_면적(ha)             |
| vldpha_Rfld5_Area  | 유효인산 논201~250이하<br><br>_면적    | 8            | 1            | 181           | 유효인산 논201~250이하<br><br>_면적(ha)  ※원문 오타 정정(아래 주1) |
| vldpha_Rfld6_Area  | 유효인산 논251이상_면적                | 8            | 1            | 922           | 유효인산 논251이상_면적(ha)                         |
| vldpha_Pfld1_Area  | 유효인산 밭200이하_면적                | 8            | 1            | 1013          | 유효인산 밭200이하_면적(ha)                         |
| vldpha_Pfld2_Area  | 유효인산 밭201~300<br><br>이하_면적    | 8            | 1            | 558           | 유효인산 밭201~300<br><br>이하_면적(ha)             |
| vldpha_Pfld3_Area  | 유효인산 밭301~400이하<br><br>_면적    | 8            | 1            | 778           | 유효인산 밭301~400이하<br><br>_면적(ha)             |
| vldpha_Pfld4_Area  | 유효인산 밭401~500이하<br><br>_면적    | 8            | 1            | 681           | 유효인산 밭401~500이하<br><br>_면적(ha)             |
| vldpha_Pfld5_Area  | 유효인산 밭501~600이하<br><br>_면적    | 8            | 1            | 801           | 유효인산 밭501~600이하<br><br>_면적(ha)             |
| vldpha_Pfld6_Area  | 유효인산 밭601이상_면적                | 8            | 1            | 6765          | 유효인산 밭601이상_면적(ha)                         |
| vldpha_Fachs1_Area | 유효인산 시설400이하_<br><br>면적       | 8            | 1            | 111           | 유효인산 시설400이하_<br><br>면적(ha)                |
| vldpha_Fachs2_Area | 유효인산 시설401~800<br><br>이하_면적   | 8            | 1            | 179           | 유효인산 시설401~800<br><br>이하_면적(ha)            |
| vldpha_Fachs3_Area | 유효인산 시설801~1200<br><br>이하_면적  | 8            | 1            | 225           | 유효인산 시설801~1200<br><br>이하_면적(ha)           |
| vldpha_Fachs4_Area | 유효인산 시설1201~1600<br><br>이하_면적 | 8            | 1            | 184           | 유효인산 시설1201~1600<br><br>이하_면적(ha)          |
| vldpha_Fachs5_Area | 유효인산 시설1601~2000<br><br>이하_면적 | 8            | 1            | 186           | 유효인산 시설1601~2000<br><br>이하_면적(ha)          |
| vldpha_Fachs6_Area | 유효인산 시설2001이상_<br><br>면적      | 8            | 1            | 1292          | 유효인산 시설2001이상_<br><br>면적(ha)               |
| vldpha_Fruit1_Area | 유효인산 과수200이하<br><br>_면적       | 8            | 1            | 40            | 유효인산 과수200이하<br><br>_면적(ha)                |
| vldpha_Fruit2_Area | 유효인산 과수201~300<br><br>이하_면적   | 8            | 1            | 19            | 유효인산 과수201~300<br><br>이하_면적(ha)            |
| vldpha_Fruit3_Area | 유효인산 과수301~400<br><br>이하_면적   | 8            | 1            | 18            | 유효인산 과수301~400<br><br>이하_면적(ha)            |
| vldpha_Fruit4_Area | 유효인산 과수401~500<br><br>이하_면적   | 8            | 1            | 26            | 유효인산 과수401~500<br><br>이하_면적(ha)            |
| vldpha_Fruit5_Area | 유효인산 과수501~600<br><br>이하_면적   | 8            | 1            | 22            | 유효인산 과수501~600<br><br>이하_면적(ha)            |
| vldpha_Fruit6_Area | 유효인산 과수601이상_<br><br>면적       | 8            | 1            | 248           | 유효인산 과수601이상_<br><br>면적(ha)                |

> **주1 — 원문 오타 정정(2026-07-26)**: 공식 명세서 원문은 `vldpha_Rfld5_Area`를
> "유효인산 논**251**~250이하"로 적고 있다. 하한이 상한보다 크므로 성립하지 않고, 4번째가
> 151~200 / 6번째가 251이상이므로 실제 구간은 **201~250**이다. 원문대로 구간중점을 계산하면
> 225.5 대신 250.5가 되어 그 구간 면적만큼 지역 평균이 위로 밀린다.
> 코드: `backend/app/infra/public_api/soil_chem_stat_client.py`의 `AP_RANGES_PADDY`.
>
> **주2 — 개방구간 대표값**: 최상단("N이상")·최하단("N이하")은 폭이 없다. 이론 상한
> (pH 14, 인산 9999)을 중점으로 쓰면 값이 폭주한다 — 실측 확인 결과 고창군 밭 유효인산
> 최상단 구간(601이상)이 6,765ha로 가장 넓어서, 상한 9999를 쓰면 지역 평균이 **2008 mg/kg**
> 이 나왔다(한국 밭 실제 400~600). 구현은 **직전 구간과 같은 폭**을 가정한다(구간자료 평균의
> 통상 관례). 이 때문에 산출값은 지역 근사이며 확정 실측이 아니다(§18-4 — UI 표기 필요).
>
> **주3 — 응답 헤더 케이스**: 이 API의 헤더 태그는 `result_Code`/`result_Msg`(**소문자 r**)다.
> 같은 data.go.kr의 토양특성 단면정보·토양검정 화학성은 `Result_Code`(대문자 R)로 다르다.
> XML 파싱은 대소문자를 구분하므로 이걸 틀리면 **성공 응답이 전부 에러로 둔갑한다** —
> 실제로 그 버그가 있었다. `base.fetch_items`가 대소문자를 무시해 흡수한다.
>
> **주4 — 조사연도 없음**: 응답 항목이 `stdg_Cd`, `bjd_Nm`, 구간별 면적뿐이라 **조사연도를
> 알 수 없다.** 없는 값을 채우지 않고, 이 값을 쓰는 화면은 "조사연도 미상 · 읍면동 평균"을
> 병기해야 한다(§1-4).
>
> **주5 — 경지구분별 구간이 다르다**: 논(`Rfld`)·밭(`Pfld`)·시설(`Fachs`)·과수(`Fruit`)의
> 구간 경계가 지표마다 서로 다르다(예: pH 시설은 5.0이하/5.1~5.5/…/7.1이상로 논밭과 다름).
> 하나의 구간표를 네 경지구분에 돌려쓰면 안 된다. 현재 구현은 논·밭만 쓴다.

---

## 4. GET /getFarmExamKalInfo — 농경지화학성_칼륨 통계 정보 조회
설명: 법정동코드(10자리)로 칼륨 통계 정보 조회

**호출코드**: GET [https://apis.data.go.kr/1390802/SoilEnviron/SoilExamStat/V2/getFarmExamKalInfo?serviceKey=발급받은인증키&STDG_CD=법정동코드10자리]
**요청 파라미터**: serviceKey(string, Y), STDG_CD(string, Y) — 상동

**응답 결과 코드**: 공통 응답 코드 표와 동일

**응답 Body 구조 (item)**
- `stdg_Cd`, `bjd_Nm`
- `posifertk_Rfld1_Area` ~ `posifertk_Rfld6_Area` (number)
- `posifertk_Pfld1_Area` ~ `posifertk_Pfld6_Area` (number)
- `posifertk_Fachs1_Area` ~ `posifertk_Fachs6_Area` (number)
- `posifertk_Fruit1_Area` ~ `posifertk_Fruit6_Area` (number)
- header: `result_Code`(string), `result_Msg`(string) ※ 이 API만 result_Code 타입이 string

| 항목명(영문)               | 항목명(국문)                     | 항목<br><br>크기 | 항목<br><br>구분 | 샘플<br><br>데이터 | 항목설명                                       |
| --------------------- | --------------------------- | ------------ | ------------ | ------------- | ------------------------------------------ |
| result_Code           | 결과코드                        | 3            | 1            | 200           | 결과코드                                       |
| result_Msg            | 결과메세지                       | 50           | 1            | OK            | 결과메시지                                      |
| stdg_Cd               | 법정동코드                       | 10           | 1            | 5279000000    | 시도,시군구,읍면동 법정동코드 값<br><br>* 행안부, 행정표준코드 참조 |
| bjd_Nm                | 법정동명                        | 50           | 1            | 전라북도 고창군      | 법정동명                                       |
| posifertk_Rfld1_Area  | 칼륨 논0.1이하_면적                | 8            | 1            | 375           | 칼륨 논0.1이하_면적(ha)                           |
| posifertk_Rfld2_Area  | 칼륨 논0.11~0.20이하_<br><br>면적  | 8            | 1            | 2224          | 칼륨 논0.11~0.20이하_<br><br>면적(ha)             |
| posifertk_Rfld3_Area  | 칼륨 논0.21~0.30이하_<br><br>면적  | 8            | 1            | 2836          | 칼륨 논0.21~0.30이하_<br><br>면적(ha)             |
| posifertk_Rfld4_Area  | 칼륨 논0.31~0.40이하_<br><br>면적  | 8            | 1            | 1808          | 칼륨 논0.31~0.40이하_<br><br>면적(ha)             |
| posifertk_Rfld5_Area  | 칼륨 논0.41~0.50이하_<br><br>면적  | 8            | 1            | 975           | 칼륨 논0.41~0.50이하_<br><br>면적(ha)             |
| posifertk_Rfld6_Area  | 칼륨 논0.51이상_면적               | 8            | 1            | 2153          | 칼륨 논0.51이상_면적(ha)                          |
| posifertk_Pfld1_Area  | 칼륨 밭0.30이하_면적               | 8            | 1            | 187           | 칼륨 밭0.30이하_면적(ha)                          |
| posifertk_Pfld2_Area  | 칼륨 밭0.31~0.40이하<br><br>_면적  | 8            | 1            | 334           | 칼륨 밭0.31~0.40이하<br><br>_면적(ha)             |
| posifertk_Pfld3_Area  | 칼륨 밭0.41~0.50이하<br><br>_면적  | 8            | 1            | 533           | 칼륨 밭0.41~0.50이하<br><br>_면적(ha)             |
| posifertk_Pfld4_Area  | 칼륨 밭0.51~0.60이하<br><br>_면적  | 8            | 1            | 741           | 칼륨 밭0.51~0.60이하<br><br>_면적(ha)             |
| posifertk_Pfld5_Area  | 칼륨 밭0.61~0.70이하<br><br>_면적  | 8            | 1            | 941           | 칼륨 밭0.61~0.70이하<br><br>_면적(ha)             |
| posifertk_Pfld6_Area  | 칼륨 밭0.71이상_면적               | 8            | 1            | 7859          | 칼륨 밭0.71이상_면적(ha)                          |
| posifertk_Fachs1_Area | 칼륨 시설0.50이하_<br><br>면적      | 8            | 1            | 14            | 칼륨 시설0.50이하_<br><br>면적(ha)                 |
| posifertk_Fachs2_Area | 칼륨 시설0.51~1.00<br><br>이하_면적 | 8            | 1            | 149           | 칼륨 시설0.51~1.00<br><br>이하_면적(ha)            |
| posifertk_Fachs3_Area | 칼륨 시설1.01~1.50<br><br>이하_면적 | 8            | 1            | 252           | 칼륨 시설1.01~1.50<br><br>이하_면적(ha)            |
| posifertk_Fachs4_Area | 칼륨 시설1.51~2.00<br><br>이하_면적 | 8            | 1            | 200           | 칼륨 시설1.51~2.00<br><br>이하_면적(ha)            |
| posifertk_Fachs5_Area | 칼륨 시설2.01~2.50<br><br>이하_면적 | 8            | 1            | 208           | 칼륨 시설2.01~2.50<br><br>이하_면적(ha)            |
| posifertk_Fachs6_Area | 칼륨 시설2.51이상<br><br>_면적      | 8            | 1            | 1354          | 칼륨 시설2.51이상<br><br>_면적(ha)                 |
| posifertk_Fruit1_Area | 칼륨 과수0.30이하<br><br>_면적      | 8            | 1            | 0             | 칼륨 과수0.30이하<br><br>_면적(ha)                 |
| posifertk_Fruit2_Area | 칼륨 과수0.31~0.40<br><br>이하_면적 | 8            | 1            | 21            | 칼륨 과수0.31~0.40<br><br>이하_면적(ha)            |
| posifertk_Fruit3_Area | 칼륨 과수0.41~0.50<br><br>이하_면적 | 8            | 1            | 21            | 칼륨 과수0.41~0.50<br><br>이하_면적(ha)            |
| posifertk_Fruit4_Area | 칼륨 과수0.51~0.60<br><br>이하_면적 | 8            | 1            | 13            | 칼륨 과수0.51~0.60<br><br>이하_면적(ha)            |
| posifertk_Fruit5_Area | 칼륨 과수0.61~0.70<br><br>이하_면적 | 8            | 1            | 20            | 칼륨 과수0.61~0.70<br><br>이하_면적(ha)            |
| posifertk_Fruit6_Area | 칼륨 과수0.71이상<br><br>_면적      | 8            | 1            | 303           | 칼륨 과수0.71이상<br><br>_면적(ha)                 |

---

## 5. GET /getFarmExamPhInfo — 농경지화학성_pH 통계 정보 조회
설명: 법정동코드(10자리)로 pH(산도) 통계 정보 조회

**호출코드**: GET [https://apis.data.go.kr/1390802/SoilEnviron/SoilExamStat/V2/getFarmExamPhInfo?serviceKey=발급받은인증키&STDG_CD=법정동코드10자리]
**요청 파라미터**: serviceKey(string, Y), STDG_CD(string, Y) — 상동

**응답 결과 코드**: 공통 응답 코드 표와 동일

**응답 Body 구조 (item)**
- `stdg_Cd`, `bjd_Nm`
- `acid_Rfld1_Area` ~ `acid_Rfld6_Area` (number)
- `acid_Pfld1_Area` ~ `acid_Pfld6_Area` (number)
- `acid_Fachs1_Area` ~ `acid_Fachs6_Area` (number)
- `acid_Fruit1_Area` ~ `acid_Fruit6_Area` (number)
- header: `result_Code`(0), `result_Msg`(string)

| 항목명(영문)          | 항목명(국문)                   | 항목 크기 | 항목 구분 | 샘플 데이터     | 항목 설명                                      |
| ---------------- | ------------------------- | ----- | ----- | ---------- | ------------------------------------------ |
| result_Code      | 결과코드                      | 3     | 1     | 200        | 결과코드                                       |
| result_Msg       | 결과메세지                     | 50    | 1     | OK         | 결과메시지                                      |
| stdg_Cd          | 법정동코드                     | 10    | 1     | 5279000000 | 시도,시군구,읍면동 법정동코드 값<br><br>* 행안부, 행정표준코드 참조 |
| bjd_Nm           | 법정동명                      | 50    | 1     | 전라북도 고창군   | 법정동명                                       |
| acid_Rfld1_Area  | pH 논4.5이하_면적              | 8     | 1     | 79         | pH 논4.5이하_면적(ha)                           |
| acid_Rfld2_Area  | pH 논4.6~5.0이하_면적          | 8     | 1     | 327        | pH 논4.6~5.0이하_면적(ha)                       |
| acid_Rfld3_Area  | pH 논5.1~5.5이하_면적          | 8     | 1     | 1978       | pH 논5.1~5.5이하_면적(ha)                       |
| acid_Rfld4_Area  | pH 논5.6~6.0이하_면적          | 8     | 1     | 2749       | pH 논5.6~6.0이하_면적(ha)                       |
| acid_Rfld5_Area  | pH 논6.1~6.5이하_면적          | 8     | 1     | 2651       | pH 논6.1~6.5이하_면적(ha)                       |
| acid_Rfld6_Area  | pH 논6.6이상_면적              | 8     | 1     | 1715       | pH 논6.6이상_면적(ha)                           |
| acid_Pfld1_Area  | pH 밭4.5이하_면적              | 8     | 1     | 1044       | pH 밭4.5이하_면적(ha)                           |
| acid_Pfld2_Area  | pH 밭4.6~5.0이하_면적          | 8     | 1     | 2438       | pH 밭4.6~5.0이하_면적(ha)                       |
| acid_Pfld3_Area  | pH 밭5.1~5.5이하_면적          | 8     | 1     | 1822       | pH 밭5.1~5.5이하_면적(ha)                       |
| acid_Pfld4_Area  | pH 밭5.6~6.0이하_면적          | 8     | 1     | 1517       | pH 밭5.6~6.0이하_면적(ha)                       |
| acid_Pfld5_Area  | pH 밭6.1~6.5이하_면적          | 8     | 1     | 1336       | pH 밭6.1~6.5이하_면적(ha)                       |
| acid_Pfld6_Area  | pH 밭6.6이상_면적              | 8     | 1     | 1533       | pH 밭6.6이상_면적(ha)                           |
| acid_Fachs1_Area | pH 시설5.0이하_면적             | 8     | 1     | 56         | pH 시설5.0이하_면적(ha)                          |
| acid_Fachs2_Area | pH 시설5.1~5.5이하_<br><br>면적 | 8     | 1     | 188        | pH 시설5.1~5.5이하_<br><br>면적(ha)              |
| acid_Fachs3_Area | pH 시설5.6~6.0이하_<br><br>면적 | 8     | 1     | 295        | pH 시설5.6~6.0이하_<br><br>면적(ha)              |
| acid_Fachs4_Area | pH 시설6.1~6.5이하_<br><br>면적 | 8     | 1     | 370        | pH 시설6.1~6.5이하_<br><br>면적(ha)              |
| acid_Fachs5_Area | pH 시설6.6~7.0이하_<br><br>면적 | 8     | 1     | 520        | pH 시설6.6~7.0이하_<br><br>면적(ha)              |
| acid_Fachs6_Area | pH 시설7.1이상_면적             | 8     | 1     | 637        | pH 시설7.1이상_면적(ha)                          |
| acid_Fruit1_Area | pH 과수4.5이하_면적             | 8     | 1     | 3          | pH 과수4.5이하_면적(ha)                          |
| acid_Fruit2_Area | pH 과수4.6~5.0이하_<br><br>면적 | 8     | 1     | 24         | pH 과수4.6~5.0이하_<br><br>면적(ha)              |
| acid_Fruit3_Area | pH 과수5.1~5.5이하_<br><br>면적 | 8     | 1     | 34         | pH 과수5.1~5.5이하_<br><br>면적(ha)              |
| acid_Fruit4_Area | pH 과수5.6~6.0이하_<br><br>면적 | 8     | 1     | 32         | pH 과수5.6~6.0이하_<br><br>면적(ha)              |
| acid_Fruit5_Area | pH 과수6.1~6.5이하_<br><br>면적 | 8     | 1     | 61         | pH 과수6.1~6.5이하_<br><br>면적(ha)              |
| acid_Fruit6_Area | pH 과수6.6이상_면적             | 8     | 1     | 193        | pH 과수6.6이상_면적(ha)                          |

---

## 6. GET /getFarmExamMgInfo — 농경지화학성_마그네슘 통계 정보 조회
설명: 법정동코드(10자리)로 마그네슘 통계 정보 조회

**호출코드**: GET [https://apis.data.go.kr/1390802/SoilEnviron/SoilExamStat/V2/getFarmExamMgInfo?serviceKey=발급받은인증키&STDG_CD=법정동코드10자리]
**요청 파라미터**: serviceKey(string, Y), STDG_CD(string, Y) — 상동

**응답 결과 코드**: 공통 응답 코드 표와 동일

**응답 Body 구조 (item)**
- `stdg_Cd`, `bjd_Nm`
- `posifertmg_Rfld1_Area` ~ `posifertmg_Rfld6_Area` (number)
- `posifertmg_Pfld1_Area` ~ `posifertmg_Pfld6_Area` (number)
- `posifertmg_Fachs1_Area` ~ `posifertmg_Fachs6_Area` (number)
- `posifertmg_Fruit1_Area` ~ `posifertmg_Fruit6_Area` (number)
- header: `result_Code`(string), `result_Msg`(string)

| 항목명(영문)                | 항목명(국문)                     | 항목<br><br>크기 | 항목<br><br>구분 | 샘플<br><br>데이터 | 항목설명                                       |
| ---------------------- | --------------------------- | ------------ | ------------ | ------------- | ------------------------------------------ |
| result_Code            | 결과코드                        | 3            | 1            | 200           | 결과코드                                       |
| result_Msg             | 결과메세지                       | 50           | 1            | OK            | 결과메시지                                      |
| stdg_Cd                | 법정동코드                       | 10           | 1            | 5279000000    | 시도,시군구,읍면동 법정동코드 값<br><br>* 행안부, 행정표준코드 참조 |
| bjd_Nm                 | 법정동명                        | 50           | 1            | 전라북도 고창군      | 법정동명                                       |
| posifertmg_Rfld1_Area  | 마그네슘 논0.5이하<br><br>_면적      | 8            | 1            | 134           | 마그네슘 논0.5이하_면적(ha)                         |
| posifertmg_Rfld2_Area  | 마그네슘 논0.6~1.0<br><br>이하_면적  | 8            | 1            | 1830          | 마그네슘 논0.6~1.0이하_면적<br><br>(ha)             |
| posifertmg_Rfld3_Area  | 마그네슘 논1.1~1.5<br><br>이하_면적  | 8            | 1            | 3810          | 마그네슘 논1.1~1.5이하_면적<br><br>(ha)             |
| posifertmg_Rfld4_Area  | 마그네슘 논1.6~2.0<br><br>이하_면적  | 8            | 1            | 2107          | 마그네슘 논1.6~2.0이하_면적<br><br>(ha)             |
| posifertmg_Rfld5_Area  | 마그네슘 논2.1~2.5<br><br>이하_면적  | 8            | 1            | 1198          | 마그네슘 논2.1~2.5이하_면적<br><br>(ha)             |
| posifertmg_Rfld6_Area  | 마그네슘 논2.6이상<br><br>_면적      | 8            | 1            | 1291          | 마그네슘 논2.6이상_면적(ha)                         |
| posifertmg_Pfld1_Area  | 마그네슘 밭0.5이하<br><br>_면적      | 8            | 1            | 948           | 마그네슘 밭0.5이하_면적(ha)                         |
| posifertmg_Pfld2_Area  | 마그네슘 밭0.6~1.0<br><br>이하_면적  | 8            | 1            | 2269          | 마그네슘 밭0.6~1.0이하_면적<br><br>(ha)             |
| posifertmg_Pfld3_Area  | 마그네슘 밭1.1~1.5<br><br>이하_면적  | 8            | 1            | 2540          | 마그네슘 밭1.1~1.5이하_면적<br><br>(ha)             |
| posifertmg_Pfld4_Area  | 마그네슘 밭1.6~2.0<br><br>이하_면적  | 8            | 1            | 1930          | 마그네슘 밭1.6~2.0이하_면적<br><br>(ha)             |
| posifertmg_Pfld5_Area  | 마그네슘 밭2.1~2.5<br><br>이하_면적  | 8            | 1            | 1261          | 마그네슘 밭2.1~2.5이하_면적<br><br>(ha)             |
| posifertmg_Pfld6_Area  | 마그네슘 밭2.6이상<br><br>_면적      | 8            | 1            | 1648          | 마그네슘 밭2.6이상_면적(ha)                         |
| posifertmg_Fachs1_Area | 마그네슘 시설0.5<br><br>이하_면적     | 8            | 1            | 15            | 마그네슘 시설0.5이하_면적<br><br>(ha)                |
| posifertmg_Fachs2_Area | 마그네슘 시설<br><br>0.6~1.0이하_면적 | 8            | 1            | 53            | 마그네슘 시설0.6~1.0이하<br><br>_면적(ha)            |
| posifertmg_Fachs3_Area | 마그네슘 시설<br><br>1.1~1.5이하_면적 | 8            | 1            | 145           | 마그네슘 시설1.1~1.5이하<br><br>_면적(ha)            |
| posifertmg_Fachs4_Area | 마그네슘 시설<br><br>1.6~2.0이하_면적 | 8            | 1            | 228           | 마그네슘 시설1.6~2.0이하<br><br>_면적(ha)            |
| posifertmg_Fachs5_Area | 마그네슘 시설<br><br>2.1~2.5이하_면적 | 8            | 1            | 390           | 마그네슘 시설2.1~2.5이하<br><br>_면적(ha)            |
| posifertmg_Fachs6_Area | 마그네슘 시설<br><br>2.6이상_면적     | 8            | 1            | 1346          | 마그네슘 시설2.6이상_면적<br><br>(ha)                |
| posifertmg_Fruit1_Area | 마그네슘 과수0.5<br><br>이하_면적     | 8            | 1            | 17            | 마그네슘 과수0.5이하_면적<br><br>(ha)                |
| posifertmg_Fruit2_Area | 마그네슘 과수<br><br>0.6~1.0이하_면적 | 8            | 1            | 56            | 마그네슘 과수0.6~1.0이하<br><br>_면적(ha)            |
| posifertmg_Fruit3_Area | 마그네슘 과수<br><br>1.1~1.5이하_면적 | 8            | 1            | 61            | 마그네슘 과수1.1~1.5이하<br><br>_면적(ha)            |
| posifertmg_Fruit4_Area | 마그네슘 과수<br><br>1.6~2.0이하_면적 | 8            | 1            | 75            | 마그네슘 과수1.6~2.0이하<br><br>_면적(ha)            |
| posifertmg_Fruit5_Area | 마그네슘 과수<br><br>2.1~2.5이하_면적 | 8            | 1            | 61            | 마그네슘 과수2.1~2.5이하<br><br>_면적(ha)            |
| posifertmg_Fruit6_Area | 마그네슘 과수<br><br>2.6이상_면적     | 8            | 1            | 107           | 마그네슘 과수2.6이상_면적<br><br>(ha)                |

---

## 7. GET /getFarmExamSaInfo — 농경지화학성_유효규산 통계 정보 조회
설명: 법정동코드(10자리)로 유효규산 통계 정보 조회

**호출코드**: GET [https://apis.data.go.kr/1390802/SoilEnviron/SoilExamStat/V2/getFarmExamSaInfo?serviceKey=발급받은인증키&STDG_CD=법정동코드10자리]
**요청 파라미터**: serviceKey(string, Y), STDG_CD(string, Y) — 상동

**응답 결과 코드**: 공통 응답 코드 표와 동일

**응답 Body 구조 (item)** — ※ 다른 API와 달리 `Rfld`(논) 항목만 존재
- `stdg_Cd`, `bjd_Nm`
- `vldsia_Rfld1_Area` ~ `vldsia_Rfld6_Area` (number)
- header: `result_Code`(string), `result_Msg`(string)

| 항목명(영문)           | 항목명(국문)                    | 항목<br><br>크기 | 항목<br><br>구분 | 샘플<br><br>데이터 | 항목설명                                       |
| ----------------- | -------------------------- | ------------ | ------------ | ------------- | ------------------------------------------ |
| result_Code       | 결과코드                       | 3            | 1            | 200           | 결과코드                                       |
| result_Msg        | 결과메세지                      | 50           | 1            | OK            | 결과메시지                                      |
| stdg_Cd           | 법정동코드                      | 10           | 1            | 5279000000    | 시도,시군구,읍면동 법정동코드 값<br><br>* 행안부, 행정표준코드 참조 |
| bjd_Nm            | 법정동명                       | 50           | 1            | 전라북도 고창군      | 법정동명                                       |
| vldsia_Rfld1_Area | 유효규산 논50이하<br><br>_면적      | 8            | 1            | 493           | 유효규산 논50이하<br><br>_면적(ha)                  |
| vldsia_Rfld2_Area | 유효규산 논51~100이하<br><br>_면적  | 8            | 1            | 2505          | 유효규산 논51~100이하<br><br>_면적(ha)              |
| vldsia_Rfld3_Area | 유효규산 논101~150<br><br>이하_면적 | 8            | 1            | 2870          | 유효규산 논101~150<br><br>이하_면적(ha)             |
| vldsia_Rfld4_Area | 유효규산 논151~200<br><br>이하_면적 | 8            | 1            | 1527          | 유효규산 논151~200<br><br>이하_면적(ha)             |
| vldsia_Rfld5_Area | 유효규산 논201~250<br><br>이하_면적 | 8            | 1            | 1135          | 유효규산 논201~250<br><br>이하_면적(ha)             |
| vldsia_Rfld6_Area | 유효규산 논251이상<br><br>_면적     | 8            | 1            | 1831          | 유효규산 논251이상<br><br>_면적(ha)                 |

---

## 8. GET /getFarmExamCalInfo — 농경지화학성_칼슘 통계 정보 조회
설명: 법정동코드(10자리)로 칼슘 통계 정보 조회

**호출코드**: GET [https://apis.data.go.kr/1390802/SoilEnviron/SoilExamStat/V2/getFarmExamCalInfo?serviceKey=발급받은인증키&STDG_CD=법정동코드10자리]
**요청 파라미터**: serviceKey(string, Y), STDG_CD(string, Y) — 상동

**응답 결과 코드**: 공통 응답 코드 표와 동일

**응답 Body 구조 (item)**
- `stdg_Cd`, `bjd_Nm`
- `posifertca_Rfld1_Area` ~ `posifertca_Rfld6_Area` (number)
- `posifertca_Pfld1_Area` ~ `posifertca_Pfld6_Area` (number)
- `posifertca_Fachs1_Area` ~ `posifertca_Fachs6_Area` (number)
- `posifertca_Fruit1_Area` ~ `posifertca_Fruit6_Area` (number)
- header: `result_Code`(0), `result_Msg`(string)

| 항목명(영문)                | 항목명(국문)                    | 항목<br><br>크기 | 항목<br><br>구분 | 샘플<br><br>데이터 | 항목설명                                       |
| ---------------------- | -------------------------- | ------------ | ------------ | ------------- | ------------------------------------------ |
| result_Code            | 결과코드                       | 3            | 1            | 200           | 결과코드                                       |
| result_Msg             | 결과메세지                      | 50           | 1            | OK            | 결과메시지                                      |
| stdg_Cd                | 법정동코드                      | 10           | 1            | 5279000000    | 시도,시군구,읍면동 법정동코드 값<br><br>* 행안부, 행정표준코드 참조 |
| bjd_Nm                 | 법정동명                       | 50           | 1            | 전라북도 고창군      | 법정동명                                       |
| posifertca_Rfld1_Area  | 칼슘 논2.0이하_면적               | 8            | 1            | 233           | 칼슘 논2.0이하_면적(ha)                           |
| posifertca_Rfld2_Area  | 칼슘 논2.1~3.0이하_<br><br>면적   | 8            | 1            | 1156          | 칼슘 논2.1~3.0이하_<br><br>면적(ha)               |
| posifertca_Rfld3_Area  | 칼슘 논3.1~4.0이하_<br><br>면적   | 8            | 1            | 2697          | 칼슘 논3.1~4.0이하_<br><br>면적(ha)               |
| posifertca_Rfld4_Area  | 칼슘 논4.1~5.0이하_<br><br>면적   | 8            | 1            | 2898          | 칼슘 논4.1~5.0이하_<br><br>면적(ha)               |
| posifertca_Rfld5_Area  | 칼슘 논5.1~6.0이하_<br><br>면적   | 8            | 1            | 1691          | 칼슘 논5.1~6.0이하_<br><br>면적(ha)               |
| posifertca_Rfld6_Area  | 칼슘 논6.1이상_면적               | 8            | 1            | 1694          | 칼슘 논6.1이상_면적(ha)                           |
| posifertca_Pfld1_Area  | 칼슘 밭3.0이하_면적               | 8            | 1            | 1333          | 칼슘 밭3.0이하_면적(ha)                           |
| posifertca_Pfld2_Area  | 칼슘 밭3.1~4.0이하_<br><br>면적   | 8            | 1            | 1546          | 칼슘 밭3.1~4.0이하_<br><br>면적(ha)               |
| posifertca_Pfld3_Area  | 칼슘 밭4.1~5.0이하_<br><br>면적   | 8            | 1            | 2079          | 칼슘 밭4.1~5.0이하_<br><br>면적(ha)               |
| posifertca_Pfld4_Area  | 칼슘 밭5.1~6.0이하_<br><br>면적   | 8            | 1            | 1866          | 칼슘 밭5.1~6.0이하_<br><br>면적(ha)               |
| posifertca_Pfld5_Area  | 칼슘 밭6.1~7.0이하_<br><br>면적   | 8            | 1            | 1288          | 칼슘 밭6.1~7.0이하_<br><br>면적(ha)               |
| posifertca_Pfld6_Area  | 칼슘 밭7.1이상_면적               | 8            | 1            | 2484          | 칼슘 밭7.1이상_면적(ha)                           |
| posifertca_Fachs1_Area | 칼슘 시설4.0이하_<br><br>면적      | 8            | 1            | 29            | 칼슘 시설4.0이하_<br><br>면적(ha)                  |
| posifertca_Fachs2_Area | 칼슘 시설4.1~5.5이하<br><br>_면적  | 8            | 1            | 68            | 칼슘 시설4.1~5.5이하<br><br>_면적(ha)              |
| posifertca_Fachs3_Area | 칼슘 시설5.6~7.0이하<br><br>_면적  | 8            | 1            | 142           | 칼슘 시설5.6~7.0이하<br><br>_면적(ha)              |
| posifertca_Fachs4_Area | 칼슘 시설7.1~8.5이하<br><br>_면적  | 8            | 1            | 292           | 칼슘 시설7.1~8.5이하<br><br>_면적(ha)              |
| posifertca_Fachs5_Area | 칼슘 시설8.6~10.0<br><br>이하_면적 | 8            | 1            | 324           | 칼슘 시설8.6~10.0<br><br>이하_면적(ha)             |
| posifertca_Fachs6_Area | 칼슘 시설10.1이상_<br><br>면적     | 8            | 1            | 1324          | 칼슘 시설10.1이상_<br><br>면적(ha)                 |
| posifertca_Fruit1_Area | 칼슘 과수3.0이하_<br><br>면적      | 8            | 1            | 38            | 칼슘 과수3.0이하_<br><br>면적(ha)                  |
| posifertca_Fruit2_Area | 칼슘 과수3.1~4.0이하<br><br>_면적  | 8            | 1            | 29            | 칼슘 과수3.1~4.0이하<br><br>_면적(ha)              |
| posifertca_Fruit3_Area | 칼슘 과수4.1~5.0이하<br><br>_면적  | 8            | 1            | 23            | 칼슘 과수4.1~5.0이하<br><br>_면적(ha)              |
| posifertca_Fruit4_Area | 칼슘 과수5.1~6.0이하<br><br>_면적  | 8            | 1            | 34            | 칼슘 과수5.1~6.0이하<br><br>_면적(ha)              |
| posifertca_Fruit5_Area | 칼슘 과수6.1~7.0이하<br><br>_면적  | 8            | 1            | 46            | 칼슘 과수6.1~7.0이하<br><br>_면적(ha)              |
| posifertca_Fruit6_Area | 칼슘 과수7.1이상_<br><br>면적      | 8            | 1            | 208           | 칼슘 과수7.1이상_<br><br>면적(ha)                  |