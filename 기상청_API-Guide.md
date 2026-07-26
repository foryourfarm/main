
## 지상 및 AWS 일통계 자료 조회

**URL** = https://apihub.kma.go.kr/api/typ01/url/sfc_aws_day.php?tm2=20150406&obs=ta_max&stn=0&disp=0&help=1&authKey=obHO9_CSRVWxzvfwktVVZQ
##### 요청인자

|인자명|의미|설명|
|---|---|---|
|tm1|년월일시분(KST)  <br>년월일(KST)|기간: 시작시간 또는 시작일 (없으면 현재시간)|
|tm2|년월일시분(KST)  <br>년월일(KST)|기간: 종료시간 또는 종료일 (없으면 현재시간)|
|obs|기상요소|rn_day : 일강수량, ta_max : 일 최고기온  <br>ta_max_dif : 최고기온차(오늘-어제), ta_max_min : 일교차  <br>ta_min : 일 최저기온, ta_min_dif : 최저기온차(오늘-어제)  <br>ws_max : 일 최대풍속, ws_ins_max : 일 최대 순간풍속  <br>sd_tot_max : 최심적설, sd_day_max : 최심 신적설|
|stn|지점번호|해당 지점들(:로 구분)의 정보 표출 (0 이거나 없으면 전체지점)|
|help|도움말추가|1 이면 필드에 대한 약간의 도움말 추가 (0 이거나 없으면 없음)|
|authKey|인증키|발급된 API 인증키|

##### 출력결과

|변수명|의미(단위)|변수명|의미(단위)|
|---|---|---|---|
|TM|관측시각 (KST)|STN|국내 지점번호|
|LON|경도 (deg)|LAT|위도 (deg)|
|HT|노장 해발고도 (m)|VAL|조회된 값|

## 방재기상연보 조회

### 방재기상 관측지점 일람표 조회

**URL** = https://apihub.kma.go.kr/api/typ02/openApi/AwsYearlyInfoService/getAwsStnLstTbl?pageNo=1&numOfRows=10&dataType=XML&year=2016&month=09&authKey=obHO9_CSRVWxzvfwktVVZQ
##### 요청인자

|인자명|의미|설명|
|---|---|---|
|pageNo|페이지 번호|페이지번호|
|numOfRows|한 페이지 결과 수|한 페이지 결과 수|
|dataType|응답자료형식|요청자료형식(XML/JSON)|
|year|발표년도|2016년 발표|
|month|발표월|09월 발표|
|authKey|인증키|발급된 API 인증키|

##### 출력결과

| 변수명        | 의미(단위)     | 변수명       | 의미(단위)  |
| ---------- | ---------- | --------- | ------- |
| resultCode | 결과코드       | resultMsg | 결과메시지   |
| numOfRows  | 한 페이지 결과 수 | pageNo    | 페이지 번호  |
| totalCount | 전체 결과 수    | dataType  | 데이터 타입  |
| stn_id     | 지역코드       | stn_ko    | 지역명(국문) |
| stn_en     | 지역명(영문)    | lat       | 북위      |
| lon        | 동경         | ht        | 해발고도    |

---
### 지점별 연요약 자료조회

**URL** = https://apihub.kma.go.kr/api/typ02/openApi/AwsYearlyInfoService/getYearSumry?pageNo=1&numOfRows=10&dataType=XML&year=2016&month=09&authKey=obHO9_CSRVWxzvfwktVVZQ
##### 요청인자

|인자명|의미|설명|
|---|---|---|
|pageNo|페이지 번호|페이지번호|
|numOfRows|한 페이지 결과 수|한 페이지 결과 수|
|dataType|응답자료형식|요청자료형식(XML/JSON)|
|year|발표년도|2016년 발표|
|month|발표월|09월 발표|
|authKey|인증키|발급된 API 인증키|

##### 출력결과

| 변수명        | 의미(단위)      | 변수명       | 의미(단위)     |
| ---------- | ----------- | --------- | ---------- |
| resultCode | 결과코드        | resultMsg | 결과메시지      |
| numOfRows  | 한 페이지 결과 수  | pageNo    | 페이지 번호     |
| totalCount | 전체 결과 수     | dataType  | 데이터 타입     |
| stn_id     | 지점번호        | stn_ko    | 지점명(국문)    |
| taDay      | 기온 평균       | taMaxAvg  | 최저 기온의 평균  |
| taMaxDay   | 연최고기온 나타난날  | taMax     | 연최고기온      |
| taMinAvg   | 연최저기온 평균    | taMin     | 기온-최저      |
| taMinDay   | 연최저기온 나타난 날 | wsDay     | 연평균풍속      |
| wsInsMax   | 연최대순간풍속     | wdInsMax  | 연최대순간풍속 풍향 |
| wsInsMaxTm | 연최대순간풍속 나타난 | rnDay     | 연 총 강수량    |
| rn1hrMax   | 연 시간 최다 강수량 |           |            |

---

### 지점별 월요약 자료조회

**URL** = [https://apihub.kma.go.kr/api/typ02/openApi/AwsYearlyInfoService/getYearSumry?pageNo=1&numOfRows=10&dataType=XML&year=2016&month=09&authKey=obHO9_CSRVWxzvfwktVVZQ](https://apihub.kma.go.kr/api/typ02/openApi/AwsYearlyInfoService/getStnbyMmSumry?pageNo=1&numOfRows=10&dataType=XML&year=2016&month=09&station=96&authKey=obHO9_CSRVWxzvfwktVVZQ)
##### 요청인자

| 인자명       | 의미         | 설명               |
| --------- | ---------- | ---------------- |
| pageNo    | 페이지 번호     | 페이지번호            |
| numOfRows | 한 페이지 결과 수 | 한 페이지 결과 수       |
| dataType  | 응답자료형식     | 요청자료형식(XML/JSON) |
| year      | 발표년도       | ‘2016년 발표’       |
| month     | 발표월        | ‘16년09월 발표’      |
| station   | 지역 코드      | ‘096지역’          |
| authKey   | 인증키        | 발급된 API 인증키      |

##### 출력결과

| 변수명          | 의미(단위)         | 변수명       | 의미(단위)     |
| ------------ | -------------- | --------- | ---------- |
| resultCode   | 결과코드           | resultMsg | 결과메시지      |
| numOfRows    | 한 페이지 결과 수     | pageNo    | 페이지 번호     |
| totalCount   | 전체 결과 수        | dataType  | 데이터 타입     |
| stn_id       | 관측 지점 번호       | stn_ko    | 관측 지점명(국문) |
| stn_en       | 관측 지점명(영문)     | str       | 항목이름       |
| taDay{month} | 항목 별 값(단위 0.1) |           |            |

---

## 방재기상월보 조회

### 방재기상 관측지점 일람표 조회

**URL** = https://apihub.kma.go.kr/api/typ02/openApi/AwsMtlyInfoService/getAwsStnLstTbl?pageNo=1&numOfRows=10&dataType=XML&year=2016&month=09&authKey=obHO9_CSRVWxzvfwktVVZQ
##### 요청인자

|인자명|의미|설명|
|---|---|---|
|pageNo|페이지 번호|페이지번호|
|numOfRows|한 페이지 결과 수|한 페이지 결과 수|
|dataType|응답자료형식|요청자료형식(XML/JSON)|
|year|발표년도|2016년 발표|
|month|발표월|09월 발표|
|authKey|인증키|발급된 API 인증키|

##### 출력결과

|변수명|의미(단위)|변수명|의미(단위)|
|---|---|---|---|
|resultCode|결과코드|resultMsg|결과메시지|
|numOfRows|한 페이지 결과 수|pageNo|페이지 번호|
|totalCount|전체 결과 수|dataType|데이터 타입|
|stn_id|지역코드|stn_ko|지역명(국문)|
|stn_en|지역명(영문)|lat|북위|
|lon|동경|ht|해발고도|
### 일별 방재기상 관측자료 조회

**URL** = https://apihub.kma.go.kr/api/typ02/openApi/AwsMtlyInfoService/getDailyAwsData?pageNo=1&numOfRows=10&dataType=XML&year=2016&month=09&station=129&authKey=obHO9_CSRVWxzvfwktVVZQ
##### 요청인자

|인자명|의미|설명|
|---|---|---|
|pageNo|페이지 번호|페이지번호|
|numOfRows|한 페이지 결과 수|한 페이지 결과 수|
|dataType|응답자료형식|요청자료형식(XML/JSON)|
|year|발표년도|2016년 발표|
|month|발표월|09월 발표|
|station|지역 코드|지역 코드|
|authKey|인증키|발급된 API 인증키|

##### 출력결과

|변수명|의미(단위)|변수명|의미(단위)|
|---|---|---|---|
|resultCode|결과코드|resultMsg|결과메시지|
|numOfRows|한 페이지 결과 수|pageNo|페이지 번호|
|totalCount|전체 결과 수|dataType|데이터 타입|
|stn_id|관측 지점 번호|stn_ko|관측 지점명(국문)|
|stn_en|관측 지점명(영문)|info-tm|날짜|
|info-ta_day|평균 기온|info-ta_max|최고 기온|
|info-ta_min|최저 기온|info-wd_day|평균풍속|
|info-ws_ins_max|최대순간 풍속|info-wd_ins_max|최대순간 풍향|
|info-rn_day|강수량|