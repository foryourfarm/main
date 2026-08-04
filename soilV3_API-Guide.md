# 토양도 기반 토양특성 단면정보V3 OpenAPI 기술명세서 (ver 1.0)

> **제공기관:** 국립농업과학원 기획조정과  
> **서비스 담당자:** 이선영 (sun028@korea.kr / 063-238-2154)  
> **데이터 갱신주기:** 분기 1회  

---

## 1. 서비스 개요

- **API명(국문):** 토양도 기반 토양특성 단면정보V3 제공 오픈API 조회 서비스
- **API명(영문):** SoilEnviron/SoilCharacSctnn/V3
- **API 설명:** 토양환경 토양도 기반 토양부호별 토양특성 단면정보를 제공하며, 지번코드(PNU) 또는 법정동코드(동, 리) 단위 값으로 최근 3년 이내 데이터를 조회합니다.
- **기본 URL (Base URL):** `http://apis.data.go.kr/1390802/SoilEnviron/SoilCharacSctnn/V3`
- **인터페이스 표준:** REST (GET)
- **교환 데이터 표준:** XML
- **보안/인증 방식:** `serviceKey` (공공데이터포털 발급 인증키)
- **메시지 교환 유형:** Request-Response

---

## 2. 상세기능 목록

| 번호 | 상세기능명(국문) | 상세기능명(영문) | 설명 |
| :---: | :--- | :--- | :--- |
| **1** | 지번코드별 토양특성 단면정보 조회 | `getSoilCharacterSctnn` | PNU 코드 기준 최근 3년 이내 토양특성 단면 정보 1건 조회 |
| **2** | 법정동/리별 토양특성 단면정보 조회 | `getSoilCharacterSctnnList` | 법정동코드(동/리) 기준 최근 3년 이내 토양특성 단면 정보 목록 조회 |

---

## 3. 상세기능 내역

### 3.1. 지번코드별 토양특성 단면정보 조회 (`getSoilCharacterSctnn`)

- **Call Back URL:** `http://apis.data.go.kr/1390802/SoilEnviron/SoilCharacSctnn/V3/getSoilCharacterSctnn`
- **최대 메시지 사이즈:** 5000 byte
- **평균 응답 시간:** 500 ms
- **초당 최대 트랜잭션 (TPS):** 30 tps

#### 가. 요청 메시지 명세 (Request Parameter)
| 항목명(영문) | 항목명(국문) | 크기 | 항목구분 | 샘플 데이터 | 항목설명 |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `serviceKey` | 인증키 | 100 | 필수(1) | 발급받은 인증키 | 공공데이터포털에서 발급받은 인증키 |
| `PNU_CD` | 지번코드 | 19 | 필수(1) | `5115034022100750001` | 19자리 지번코드 (법정동코드 10자리 + 산/일반 1자리 + 본번 4자리 + 부번 4자리) |

#### 나. 응답 메시지 명세 (Response Field)
| 항목명(영문) | 항목명(국문) | 크기 | 항목구분 | 샘플 데이터 | 항목설명 |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `Result_Code` | 결과코드 | 3 | 필수(1) | `200` | 결과코드 |
| `Result_Msg` | 결과메세지 | 50 | 필수(1) | `OK` | 결과메시지 |
| `PNU_Cd` | 지번코드 | 19 | 필수(1) | `5115034022100750001` | 요청 지번코드 |
| `Pnu_Nm` | 대상지 지번주소 | 100 | 필수(1) | 강원특별자치도 강릉시 강동면 모전리 75-1 | 지번주소 |
| `Deepsoil_Qlt_Cd` | 심토토성코드 | 2 | 필수(1) | `04` | 심토토성 식별 ID (코드표 참조) |
| `Deepsoil_Ston_Cd` | 심토자갈함량코드 | 2 | 필수(1) | `02` | 심토자갈함량 식별 ID (코드표 참조) |
| `Soilslope_Cd` | 경사도코드 | 2 | 필수(1) | `03` | 경사도 식별 ID (코드표 참조) |

#### 다. 요청/응답 예제

**[요청 URL]**
```http
http://apis.data.go.kr/1390802/SoilEnviron/SoilCharacSctnn/V3/getSoilCharacterSctnn?serviceKey={인증키}&PNU_CD=5115034022100750001
```

**[응답 XML]**
```xml
<?xml version="1.0" encoding="UTF-8" standalone="true"?>
<response>
  <header>
    <Result_Code>200</Result_Code>
    <Result_Msg>OK</Result_Msg>
  </header>
  <body>
    <items>
      <item>
        <PNU_Cd>5115034022100750001</PNU_Cd>
        <Pnu_Nm>강원특별자치도 강릉시 강동면 모전리 75-1</Pnu_Nm>
        <Deepsoil_Qlt_Cd>04</Deepsoil_Qlt_Cd>
        <Deepsoil_Ston_Cd>02</Deepsoil_Ston_Cd>
        <Soilslope_Cd>03</Soilslope_Cd>
      </item>
    </items>
  </body>
</response>
```

---

### 3.2. 법정동/리별 토양특성 단면정보 조회 (`getSoilCharacterSctnnList`)

- **Call Back URL:** `http://apis.data.go.kr/1390802/SoilEnviron/SoilCharacSctnn/V3/getSoilCharacterSctnnList`
- **최대 메시지 사이즈:** 5000 byte
- **평균 응답 시간:** 500 ms
- **초당 최대 트랜잭션 (TPS):** 30 tps

#### 가. 요청 메시지 명세 (Request Parameter)
| 항목명(영문) | 항목명(국문) | 크기 | 항목구분 | 샘플 데이터 | 항목설명 |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `serviceKey` | 인증키 | 100 | 필수(1) | 발급받은 인증키 | 공공데이터포털에서 발급받은 인증키 |
| `Page_Size` | 한 페이지 결과 수 | 15 | 필수(1) | `10` | 한 페이지 결과 수 |
| `Page_No` | 페이지 번호 | 15 | 필수(1) | `1` | 페이지 번호 |
| `STDG_CD` | 법정동코드(동/리) | 10 | 필수(1) | `5115034022` | 10자리 법정동코드 (동/리 단위) |

#### 나. 응답 메시지 명세 (Response Field)
| 항목명(영문) | 항목명(국문) | 크기 | 항목구분 | 샘플 데이터 | 항목설명 |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `Result_Code` | 결과코드 | 3 | 필수(1) | `200` | 결과코드 |
| `Result_Msg` | 결과메세지 | 50 | 필수(1) | `OK` | 결과메시지 |
| `Rcdcnt` | 한 페이지 레코드 수 | 10 | 필수(1) | `10` | 한 페이지당 표출 데이터 레코드 수 |
| `Page_No` | 페이지 수 | 10 | 필수(1) | `1` | 페이지 번호 |
| `Total_Count` | 데이터 총 개수 | 15 | 필수(1) | `168` | 데이터 총 개수 |
| `No` | 정렬 번호 | 10 | 필수(1) | `1` | 검색 결과 정렬 번호 |
| `Stdg_Cd` | 법정동코드 | 10 | 필수(1) | `5115034022` | 요청 법정동코드 |
| `Pnu_Nm` | 대상지 지번주소 | 100 | 필수(1) | 강원특별자치도 강릉시 강동면 모전리 2 | 지번주소 |
| `Deepsoil_Qlt_Cd` | 심토토성코드 | 2 | 필수(1) | `04` | 심토토성 식별 ID (코드표 참조) |
| `Deepsoil_Ston_Cd` | 심토자갈함량코드 | 2 | 필수(1) | `02` | 심토자갈함량 식별 ID (코드표 참조) |
| `Soilslope_Cd` | 경사도코드 | 2 | 필수(1) | `03` | 경사도 식별 ID (코드표 참조) |

#### 다. 요청/응답 예제

**[요청 URL]**
```http
http://apis.data.go.kr/1390802/SoilEnviron/SoilCharacSctnn/V3/getSoilCharacterSctnnList?serviceKey={인증키}&Page_Size=10&Page_No=1&STDG_CD=5115034022
```

**[응답 XML]**
```xml
<?xml version="1.0" encoding="UTF-8" standalone="true"?>
<response>
  <header>
    <Result_Code>200</Result_Code>
    <Result_Msg>OK</Result_Msg>
  </header>
  <body>
    <Rcdcnt>10</Rcdcnt>
    <Page_No>1</Page_No>
    <Total_Count>168</Total_Count>
    <items>
      <item>
        <No>1</No>
        <Stdg_Cd>5115034022</Stdg_Cd>
        <Pnu_Nm>강원특별자치도 강릉시 강동면 모전리 2</Pnu_Nm>
        <Deepsoil_Qlt_Cd>04</Deepsoil_Qlt_Cd>
        <Deepsoil_Ston_Cd>02</Deepsoil_Ston_Cd>
        <Soilslope_Cd>03</Soilslope_Cd>
      </item>
      <item>
        <No>2</No>
        <Stdg_Cd>5115034022</Stdg_Cd>
        <Pnu_Nm>강원특별자치도 강릉시 강동면 모전리 1</Pnu_Nm>
        <Deepsoil_Qlt_Cd>02</Deepsoil_Qlt_Cd>
        <Deepsoil_Ston_Cd>01</Deepsoil_Ston_Cd>
        <Soilslope_Cd>01</Soilslope_Cd>
      </item>
    </items>
  </body>
</response>
```

---

## 4. OpenAPI 에러코드 정리

### 4.1. 공공데이터포털 에러코드
| 에러코드 | 에러메시지 | 설명 |
| :---: | :--- | :--- |
| **1** | `APPLICATION ERROR` | 어플리케이션 에러 |
| **4** | `HTTP ERROR` | HTTP 에러 |
| **12** | `NO OPENAPI SERVICE ERROR` | 해당 오픈API서비스가 없거나 폐기됨 |
| **20** | `SERVICE ACCESS DENIED ERROR` | 서비스 접근거부 |
| **22** | `LIMITED NUMBER OF SERVICE REQUESTS EXCEEDS ERROR` | 서비스 요청제한횟수 초과 에러 |
| **30** | `SERVICE KEY IS NOT REGISTERED ERROR` | 등록되지 않은 서비스키 |
| **31** | `DEADLINE HAS EXPIRED ERROR` | 활용기간 만료 |
| **32** | `UNREGISTERED IP ERROR` | 등록되지 않은 IP |

### 4.2. 제공기관 에러코드
| 에러코드 | 에러메시지 | 설명 |
| :---: | :--- | :--- |
| **101** | `KEY_AUTH_FAIL_ERROR` | 서비스키 인증 실패 |
| **200** | `OK` | 정상 처리 |
| **201** | `PARAM_VALI_ERROR` | 요청변수 형식이 일치하지 않은 경우 |
| **202** | `PARAM_ZERO_ERROR` | 요청변수로 0 이하 음수 값은 허용하지 않음 |
| **203** | `PARAM_NULL_ERROR` | 요청변수 값으로 null을 허용하지 않음 |
| **204** | `PARAM_ESSENTIAL_ERROR` | 필수 요청변수 미입력 |
| **301** | `OK_NO_DATA_ERROR` | 요청 데이터 없음 |
| **400** | `REQUEST_PAGE_VALI_ERROR` | 요청 페이지 형식 오류 |
| **404** | `REQUEST_PAGE_ERROR` | 요청 페이지가 존재하지 않음 |
| **500** | `SERVER_INNER_ERROR` | 내부 서버 문제 발생 |
| **600** | `PROGRAM_CODE_ERROR` | 프로그램 오류 |
| **999** | `ETC_SERVICE_ERROR` | 기타 알 수 없는 오류 |

---

## 5. 코드표 참조

### 5.1. 심토토성 코드표 (`Deepsoil_Qlt_Cd`)
| 심토토성코드 | 심토토성 |
| :---: | :--- |
| **01** | 사질 |
| **02** | 사양질 |
| **03** | 미사사양질 |
| **04** | 식양질 |
| **05** | 미사식양질 |
| **06** | 식질 |
| **99** | 기타 |

### 5.2. 심토자갈함량 코드표 (`Deepsoil_Ston_Cd`)
| 심토자갈함량코드 | 심토자갈함량 |
| :---: | :--- |
| **01** | 없음 (0-15%) |
| **02** | 있음 (15-35%) |
| **03** | 심함 (35% 이상) |
| **99** | 기타 |

### 5.3. 경사 코드표 (`Soilslope_Cd`)
| 경사코드 | 경사 |
| :---: | :--- |
| **01** | 경사 0-2% |
| **02** | 경사 2-7% |
| **03** | 경사 7-15% |
| **04** | 경사 15-30% |
| **05** | 경사 30-60% |
| **06** | 경사 60-100% |
| **99** | 기타 |
