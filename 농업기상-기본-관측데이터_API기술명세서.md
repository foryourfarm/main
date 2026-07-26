
- 제공기관: 농촌진흥청 국립농업과학원
- API 유형: REST / 데이터포맷: XML
- Base URL: `https://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather`
- 공통 인증: `serviceKey` (공공데이터포털 발급 인증키, 모든 API 필수)

> **역할(우리 프로젝트)**: **1차 데이터원**이다. 일사량(`srqty`)과 일조시간(`sun_Time`)이
> 여기에만 있어 장기 탭 일조 지표의 근거가 된다. 결측은 기상청 AWS(`기상청_API-Guide.md`)로
> 보완한다 — 단 관측망이 달라 지점코드가 조인되지 않는다(농업기상 `230802A001` vs AWS `108`).

> 공통 응답 코드: `101`(서비스키 인증 실패), `200`(성공), `201`(요청변수 형식 불일치), `202`(요청변수 음수 불허), `203`(요청변수 null 불허), `204`(필수 요청변수 미입력), `301`(요청 데이터 없음), `400`(요청 페이지 형식 오류), `404`(요청 페이지 없음), `500`(내부 서버 오류), `600`(프로그램 오류), `999`(기타 알 수 없는 오류)

> **응답 헤더 태그는 `result_Code` / `result_Msg`(소문자 r)이고 성공은 `200`이다.**
> XML 파싱은 대소문자를 구분하므로 이걸 틀리면 성공 응답이 전부 에러가 된다.
> body에는 `rcdcnt`, `page_No`, `total_Count`가 함께 온다.

> 공통 응답 모델(body.items.item): no, stn_Cd(지점코드), stn_Name(지점명), date(관측일자), temp(기온), hghst_Artmp(최고기온), lowst_Artmp(최저기온), hum(습도), widdir(풍향), wind(풍속), max_Wind(최대풍속), rn(강수량), sun_Time(일조시간), srqty(일사량), condens_Time(결로시간), gr_Temp(지면온도), soil_Temp(토양온도), soil_Wt(토양수분)

### 응답 필드 단위·형식 (원문에 없어 실호출로 확정, 2026-07-26)

원문 명세서는 필드명만 나열하고 **단위를 적지 않는다.** 특히 `sun_Time`을 시간으로 오해하면
계산이 60배 틀어지므로 아래를 기준으로 삼는다.

| 필드 | 단위·형식 | 확정 근거 |
|---|---|---|
| `stn_Cd` | 10자리 영숫자, 예 `230802A001` | 실응답 |
| `stn_Name` | `"시군구 읍면동"` 형태, 예 `"영월군 영월읍"` | 실응답. 광역시는 `"부산시 강서구"`처럼 2번째 토큰이 구다 |
| `date` | **`YYYY-MM-DD`** (하이픈 포함) | 실응답. 요청 파라미터는 하이픈 없는 `YYYYMMDD`라 형식이 다르다 |
| `temp`, `hghst_Artmp`, `lowst_Artmp` | ℃ | 실응답 |
| `hum` | % | 실응답 |
| `rn` | mm | 실응답. 결측은 `-999` 관례값 |
| **`sun_Time`** | **분(minute)** | 실측 분포 검증: 최대 793 → 시간이면 불가능, **분이면 13.2h**로 국내 최대 가조시간과 일치 |
| **`condens_Time`** | **분(minute)** | 동일 근거(757 = 12.6h) |
| `srqty` | **MJ/m²/day** | `Rs/Ra` 비율이 물리 범위(0.03~0.80)에 들어오는 것으로 확인 |
| `soil_Wt` | % | 실응답 |

**결측·품질 주의**
- `sun_Time`은 결측이 많다 — 2024년 1·4·7·10월 26,071행 중 **8,745행만 보유**. `srqty`가 더 잘 채워지므로 일조시간은 일사량에서 환산하는 것이 실용적이다(`backend/app/services/sunlight_calculation.py`).
- 빈 문자열(`<sun_Time></sun_Time>`)로 오는 결측이 있다 — `0`으로 파싱하면 안 된다.
- **센서 불량 지점이 존재한다.** 지점별로 일사량–일조 상관을 재면 65개 중 5개가 R²<0.2(기울기 음수 포함)였다. `Rs/Ra > 0.80`(청천 상한 초과)인 행도 365건 있었고 최대 2.46이었다. 진입 지점에서 걸러야 한다(§12).
- 관측지점 수는 **216개**(2024년 표본의 고유 `stn_Cd`). 문서·주석에 보이는 "510개"는 기상청 AWS 기준이며 이 API와 무관하다.
- `동방로거테스트`라는 테스트 지점이 응답에 섞여 있다 — 적재 시 제외할 것.

### 🔴 원문 오류 정정 — 기간 조회 날짜 형식 (실호출 확인, 2026-07-26)

원문은 `begin_Date`/`end_Date`를 `YYYYMMDD`(예 `20260101`)로 적고 있으나 **틀렸다.**
하이픈 없는 형식으로 보내면 `201 요청변수 형식이 일치하지 않은 경우`가 온다. 실측 결과:

| 요청 | 결과 |
|---|---|
| `begin_Date=20240701&end_Date=20240710&obsr_Spot_Cd=336812A001` | ❌ `201 요청변수 형식이 일치하지 않은 경우` |
| `begin_Date=2024-07-01&end_Date=2024-07-10&obsr_Spot_Cd=336812A001` | ✅ `200 정상`, total_Count=10 |
| 하이픈 O, `obsr_Spot_Cd` 없음 | ❌ `204 필수 요청변수 미입력` |
| 하이픈 O, `Obsr_Spot_Code`(지점정보 API 이름) 사용 | ❌ `204` — 파라미터명이 다르다 |

→ **기간 조회(`getWeatherTerm*`)는 `YYYY-MM-DD`를 쓴다.** 응답 `date`도 하이픈 형식이라
일관된다. 반면 `search_Year`/`search_Month`는 하이픈 없는 숫자다(`2024`, `07`).
`obsr_Spot_Cd`는 필수이며 지점정보 API의 `Obsr_Spot_Code`와 이름이 다르다.

### 🔴 페이지네이션 필수 — `Page_Size`를 넘는 결과는 조용히 잘린다

`Page_Size=100`으로 `getWeatherMonDayList3`(2024-07)를 호출하면 `rcdcnt=100`인데
`total_Count=6551`이다. **큰 값 하나로 때우면 안 된다** — 지점이 늘거나 기간이 길어질 때
데이터가 말없이 사라진다. `Page_No`를 올려 짧은 페이지가 올 때까지 순회해야 한다
(구현: `weather_client._fetch_all`).

원문에 상한이 명시된 것은 10분 자료(1~144)뿐이다. 실측상 `Page_Size=9999`도 받아주지만
의존하면 위험하다.

> **🔴 호출량 주의 — 엔드포인트별 쿼터**: `getWeatherYearMonList3`는 두 차례 시도 모두
> `HTTP 429 API token quota exceeded`였고, 같은 시각 `getWeatherMonDayList3`는 정상이었다.
> 즉 쿼터가 **엔드포인트별로 따로** 관리되며 년도별 월 집계 엔드포인트는 이미 소진 상태다.
> 월 집계가 필요하면 일별을 받아 직접 집계한다(`scripts/load_solar_radiation_normal.py`가
> 그렇게 한다 — 36콜로 3년치 전국 231,659행을 받았고 429가 나지 않았다).

---

## 1. GET /getWeatherTenMinList3
농업기상 조회일자별 10분 기본 관측데이터 조회

**호출코드**
```
GET https://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather/getWeatherTenMinList3?serviceKey={인증키}&Page_No=1&Page_Size=100&date=20260101&time=0900
```

**파라미터**
| 변수명 | 필수 | 타입 | 위치 | 설명 |
|---|---|---|---|---|
| serviceKey | Y | string | query | 공공데이터포털 발급 인증키 |
| Page_No | Y | number | query | 페이지 번호 |
| Page_Size | Y | number | query | 한 페이지 결과 수 (1~144 최대) |
| date | Y | string | query | 관측년월일 |
| time | N | string | query | 관측시간 |
| obsr_Spot_Nm | N | string | query | 관측지점명 |
| obsr_Spot_Cd | N | string | query | 관측지점코드 |

**결과 코드**: 공통 코드표 참조 (101, 200, 201~204, 301, 400, 404, 500, 600, 999)

---

## 2. GET /getWeatherTimeList3
농업기상 조회일자별 시간 기본 관측데이터 조회

**호출코드**
```
GET .../getWeatherTimeList3?serviceKey={인증키}&Page_No=1&Page_Size=24&date_Time=20260101
```

**파라미터**
| 변수명 | 필수 | 타입 | 위치 | 설명 |
|---|---|---|---|---|
| serviceKey | Y | string | query | 인증키 |
| Page_No | Y | number | query | 페이지 번호 |
| Page_Size | Y | number | query | 한 페이지 결과 수 |
| date_Time | Y | string | query | 관측년월일 |
| obsr_Spot_Nm | N | string | query | 관측지점명 |
| obsr_Spot_Cd | N | string | query | 관측지점코드 |

**결과 코드**: 공통 코드표 참조

---

## 3. GET /getWeatherMonDayList3
농업기상 조회월별 일 기본 관측데이터 조회

**호출코드**
```
GET .../getWeatherMonDayList3?serviceKey={인증키}&Page_No=1&Page_Size=31&search_Year=2026&search_Month=01
```

**파라미터**
| 변수명 | 필수 | 타입 | 위치 | 설명 |
|---|---|---|---|---|
| serviceKey | Y | string | query | 인증키 |
| Page_No | Y | number | query | 페이지 번호 |
| Page_Size | Y | number | query | 한 페이지 결과 수 |
| search_Year | Y | string | query | 관측년도 |
| search_Month | Y | string | query | 관측월 |
| obsr_Spot_Nm | N | string | query | 관측지점명 |
| obsr_Spot_Cd | N | string | query | 관측지점코드 |

**결과 코드**: 공통 코드표 참조

---

## 4. GET /getWeatherYearDayList3
농업기상 조회년도별 일 기본 관측데이터 조회

**호출코드**
```
GET .../getWeatherYearDayList3?serviceKey={인증키}&Page_No=1&Page_Size=365&search_Year=2026&obsr_Spot_Cd={지점코드}
```

**파라미터**
| 변수명 | 필수 | 타입 | 위치 | 설명 |
|---|---|---|---|---|
| serviceKey | Y | string | query | 인증키 |
| Page_No | Y | number | query | 페이지 번호 |
| Page_Size | Y | number | query | 한 페이지 결과 수 |
| search_Year | Y | string | query | 관측년도 |
| obsr_Spot_Cd | Y | string | query | 관측지점코드 |

**결과 코드**: 공통 코드표 참조

---

## 5. GET /getWeatherYearBsunList3
농업기상 조회년도별 반순 기본 관측데이터 조회

**호출코드**
```
GET .../getWeatherYearBsunList3?serviceKey={인증키}&Page_No=1&Page_Size=24&search_Year=2026&obsr_Spot_Cd={지점코드}
```

**파라미터**
| 변수명 | 필수 | 타입 | 위치 | 설명 |
|---|---|---|---|---|
| serviceKey | Y | string | query | 인증키 |
| Page_No | Y | number | query | 페이지 번호 |
| Page_Size | Y | number | query | 한 페이지 결과 수 |
| search_Year | Y | string | query | 관측년도 |
| obsr_Spot_Cd | Y | string | query | 관측지점코드 |

**결과 코드**: 공통 코드표 참조

---

## 6. GET /getWeatherYearSunList3
농업기상 조회년도별 순 기본 관측데이터 조회

**호출코드**
```
GET .../getWeatherYearSunList3?serviceKey={인증키}&Page_No=1&Page_Size=36&search_Year=2026&obsr_Spot_Cd={지점코드}
```

**파라미터**
| 변수명 | 필수 | 타입 | 위치 | 설명 |
|---|---|---|---|---|
| serviceKey | Y | string | query | 인증키 |
| Page_No | Y | number | query | 페이지 번호 |
| Page_Size | Y | number | query | 한 페이지 결과 수 |
| search_Year | Y | string | query | 관측년도 |
| obsr_Spot_Cd | Y | string | query | 관측지점코드 |

**결과 코드**: 공통 코드표 참조

---

## 7. GET /getWeatherYearMonList3
농업기상 조회년도별 월 기본 관측데이터 조회

**호출코드**
```
GET .../getWeatherYearMonList3?serviceKey={인증키}&Page_No=1&Page_Size=12&search_Year=2026&obsr_Spot_Cd={지점코드}
```

**파라미터**
| 변수명 | 필수 | 타입 | 위치 | 설명 |
|---|---|---|---|---|
| serviceKey | Y | string | query | 인증키 |
| Page_No | Y | number | query | 페이지 번호 |
| Page_Size | Y | number | query | 한 페이지 결과 수 |
| search_Year | Y | string | query | 관측년도 |
| obsr_Spot_Cd | Y | string | query | 관측지점코드 |

**결과 코드**: 공통 코드표 참조

---

## 8. GET /getWeatherTermDayList3
농업기상 조회기간별 일 기본 관측데이터 조회

**호출코드**
```
GET .../getWeatherTermDayList3?serviceKey={인증키}&Page_No=1&Page_Size=100&begin_Date=20260101&end_Date=20260131&obsr_Spot_Cd={지점코드}
```

**파라미터**
| 변수명 | 필수 | 타입 | 위치 | 설명 |
|---|---|---|---|---|
| serviceKey | Y | string | query | 인증키 |
| Page_No | Y | number | query | 페이지 번호 |
| Page_Size | Y | number | query | 한 페이지 결과 수 |
| begin_Date | Y | string | query | 시작일자 |
| end_Date | Y | string | query | 종료일자 (1~365일 최대 허용) |
| obsr_Spot_Cd | Y | string | query | 관측지점코드 |

**결과 코드**: 공통 코드표 참조

---

## 9. GET /getWeatherTermBsunList3
농업기상 조회기간별 반순 기본 관측데이터 조회

**호출코드**
```
GET .../getWeatherTermBsunList3?serviceKey={인증키}&Page_No=1&Page_Size=100&begin_Date=20260101&end_Date=20260131&obsr_Spot_Cd={지점코드}
```

**파라미터**
| 변수명 | 필수 | 타입 | 위치 | 설명 |
|---|---|---|---|---|
| serviceKey | Y | string | query | 인증키 |
| Page_No | Y | number | query | 페이지 번호 |
| Page_Size | Y | number | query | 한 페이지 결과 수 |
| begin_Date | Y | string | query | 시작일자 |
| end_Date | Y | string | query | 종료일자 (1~365일 최대 허용) |
| obsr_Spot_Cd | Y | string | query | 관측지점코드 |

**결과 코드**: 공통 코드표 참조

---

## 10. GET /getWeatherTermSunList3
농업기상 조회기간별 순 기본 관측데이터 조회

**호출코드**
```
GET .../getWeatherTermSunList3?serviceKey={인증키}&Page_No=1&Page_Size=100&begin_Date=20260101&end_Date=20260131&obsr_Spot_Cd={지점코드}
```

**파라미터**
| 변수명 | 필수 | 타입 | 위치 | 설명 |
|---|---|---|---|---|
| serviceKey | Y | string | query | 인증키 |
| Page_No | Y | number | query | 페이지 번호 |
| Page_Size | Y | number | query | 한 페이지 결과 수 |
| begin_Date | Y | string | query | 시작일자 |
| end_Date | Y | string | query | 종료일자 (1~365일 최대 허용) |
| obsr_Spot_Cd | Y | string | query | 관측지점코드 |

**결과 코드**: 공통 코드표 참조

---

## 11. GET /getWeatherTermMonList3
농업기상 조회기간별 월 기본 관측데이터 조회

**호출코드**
```
GET .../getWeatherTermMonList3?serviceKey={인증키}&Page_No=1&Page_Size=100&begin_Date=20260101&end_Date=20260131&obsr_Spot_Cd={지점코드}
```

**파라미터**
| 변수명 | 필수 | 타입 | 위치 | 설명 |
|---|---|---|---|---|
| serviceKey | Y | string | query | 인증키 |
| Page_No | Y | number | query | 페이지 번호 |
| Page_Size | Y | number | query | 한 페이지 결과 수 |
| begin_Date | Y | string | query | 시작일자 |
| end_Date | Y | string | query | 종료일자 (1~365일 최대 허용) |
| obsr_Spot_Cd | Y | string | query | 관측지점코드 |

**결과 코드**: 공통 코드표 참조
