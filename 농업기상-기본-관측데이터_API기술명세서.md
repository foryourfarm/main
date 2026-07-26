
- 제공기관: 농촌진흥청 국립농업과학원
- API 유형: REST / 데이터포맷: XML
- Base URL: `apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather`
- 공통 인증: `serviceKey` (공공데이터포털 발급 인증키, 모든 API 필수)

> 공통 응답 코드: `101`(서비스키 인증 실패), `200`(성공), `201`(요청변수 형식 불일치), `202`(요청변수 음수 불허), `203`(요청변수 null 불허), `204`(필수 요청변수 미입력), `301`(요청 데이터 없음), `400`(요청 페이지 형식 오류), `404`(요청 페이지 없음), `500`(내부 서버 오류), `600`(프로그램 오류), `999`(기타 알 수 없는 오류)

> 공통 응답 모델(body.items.item): no, stn_Cd(지점코드), stn_Name(지점명), date(관측일자), temp(기온), hghst_Artmp(최고기온), lowst_Artmp(최저기온), hum(습도), widdir(풍향), wind(풍속), max_Wind(최대풍속), rn(강수량), sun_Time(일조시간), srqty(일사량), condens_Time(결로시간), gr_Temp(지면온도), soil_Temp(토양온도), soil_Wt(토양수분)

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
