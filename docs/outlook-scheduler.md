# 3개월전망 자동 갱신 (Cloud Scheduler)

> 대상: 배포·운영 담당자. 프론트가 부르는 API가 아니다.
> 관련: `README.md` §배포, `nexttodo.md` 인프라, `docs/long-term-tab-api.md`

## 왜 필요한가

기상청 3개월전망은 **매월 23일 전후 1회** 발표된다. 안 받으면 장기 탭이
**에러 없이 조용히** 낡은 전망으로 채점된다 — 화면에 경고가 뜨지 않으므로 사람이
알아채는 경로가 없다. 장기 탭 3개월 창이 전망에 묶인 뒤로는 조용히 틀려지는 경로다.

종전에는 `scripts/load_weather_outlook.py`를 사람이 손으로 돌려야 했다.

## 무엇이 도는가

```
매일 06:00 KST
  Cloud Scheduler (작업 1개)
      │  POST https://<백엔드>/api/v1/admin/weather-outlooks
      │  헤더: X-Admin-Token: <시크릿>
      ▼
  Cloud Run 백엔드  ← min-instances=0이라 이 요청이 컨테이너를 깨운다
      ├─ 토큰 검사 (DB·외부 호출보다 먼저)
      ├─ ingest_latest_outlook(db, today)
      │    기상청 RSS 조회 → 권역 13개를 시/군 256개로 펼침 → uq_outlook upsert
      └─ 200 결과 / 502 실패
```

**매일 도는 이유**: 발표일이 실제로 이동한다(2026-05는 22일에 나왔다). 매일 돌리면
발표일 이동과 일시적 네트워크 실패를 자동으로 흡수한다. `uq_outlook` upsert라 같은
발표분을 며칠 연속 넣어도 무해하고, 클라이언트가 최근 2개월치를 되짚으므로 하루
놓쳐도 다음 날 복구된다.

**비용**: Cloud Scheduler는 계정당 작업 3개까지 무료(우리는 1개). Cloud Run은 월 30회
요청이라 무료 등급 안쪽이다. 계정 상태에 따라 다르므로 확정 견적은 아니다.

**콜드 스타트는 해결되지 않는다.** 매일 한 번 컨테이너가 깨지만 Cloud Run은 유휴가
되면 다시 죽는다. `min-instances=1`은 여전히 별개 결정이다(`nexttodo.md` 인프라 §7).

## 엔드포인트 계약

`POST /api/v1/admin/weather-outlooks`

| 헤더 | 필수 | 값 |
|---|---|---|
| `X-Admin-Token` | ✅ | `ADMIN_TASK_TOKEN` 환경변수와 같은 값 |

성공 (200):

```json
{
  "success": true,
  "data": {
    "published_at": "2026-07-22",
    "rows": 1536,
    "target_months": ["2026-08-01", "2026-09-01", "2026-10-01"],
    "unmapped_zones": ["평안남도"]
  },
  "error": null
}
```

`unmapped_zones`는 region 매핑이 없는 권역(북한 등)이라 **실패가 아니다.** 다만 이
목록이 갑자기 늘면 RSS 권역명이 바뀐 것이므로 응답에 실어 눈에 띄게 했다.

| 상태 | code | 언제 |
|---|---|---|
| 401 | `UNAUTHORIZED` | 헤더 없음/불일치 |
| 503 | `ADMIN_TASKS_DISABLED` | `ADMIN_TASK_TOKEN` 미설정 — **기능이 꺼진 것**이지 열려 있는 게 아니다 |
| 502 | `UPSTREAM_UNAVAILABLE` | 최근 2개월을 되짚어도 유효한 RSS 없음 → 상류 장애나 스키마 변경 |

502를 내는 이유: Cloud Scheduler가 재시도하고 로그에 남는다. 200으로 삼키면 "에러 없이
조용히 낡는" 원래 문제를 그대로 재현한다.

## 설정 (한 번만)

### 1. 백엔드에 시크릿 주입

```bash
gcloud run services update foryourfarm-backend --region asia-northeast3 --update-env-vars ADMIN_TASK_TOKEN=$(openssl rand -hex 32)
```

⚠️ `--set-env-vars`가 **아니다.** 그건 기존 env를 통째로 교체해 `JWT_SECRET`·
`CORS_ORIGINS`·공공 API 키를 전부 날린다(README §⑤).

주입한 값을 확인:

```bash
gcloud run services describe foryourfarm-backend --region asia-northeast3 --format='value(spec.template.spec.containers[0].env)'
```

### 2. 스케줄러 작업 생성

```bash
gcloud scheduler jobs create http outlook-refresh --location asia-northeast3 --schedule "0 6 * * *" --time-zone "Asia/Seoul" --uri "https://<백엔드URL>/api/v1/admin/weather-outlooks" --http-method POST --headers "X-Admin-Token=<1단계에서 만든 값>"
```

### 3. 즉시 1회 실행해 확인

```bash
gcloud scheduler jobs run outlook-refresh --location asia-northeast3
```

```bash
gcloud scheduler jobs describe outlook-refresh --location asia-northeast3 --format='value(status,lastAttemptTime)'
```

`503 ADMIN_TASKS_DISABLED`가 나오면 1단계 env가 안 들어갔거나 그 뒤 재배포에서
`--set-env-vars`로 날아간 것이다.

## 수동 갱신

스케줄러와 같은 경로를 curl로 부를 수 있다:

```bash
curl -X POST -H "X-Admin-Token: $ADMIN_TASK_TOKEN" https://<백엔드URL>/api/v1/admin/weather-outlooks
```

DB에 직접 붙을 수 있는 환경이라면 CLI도 그대로 쓸 수 있다(같은 함수를 부른다):

```bash
backend/.venv/bin/python scripts/load_weather_outlook.py
```

## 보안 판단 근거 (2026-08-02)

공개 Cloud Run 서비스에 운영 엔드포인트가 붙는다. 프론트가 이 서비스를 부르므로
`--no-allow-unauthenticated` + IAM으로는 막을 수 없어 앱 레벨 시크릿을 쓴다.

- **무단 적재는 막힌다** — 32바이트 랜덤 토큰, `secrets.compare_digest` 상수시간 비교,
  검사가 DB·RSS 호출보다 먼저 돈다.
- **볼류메트릭 DoS는 막지 않는다** — 다만 이 엔드포인트가 새로 뚫는 구멍이 아니다.
  요청당 비용이 문자열 비교 1회(DB 미접속)라, 이미 공개된 `/auth/login`(요청당 bcrypt)
  보다 몇 자릿수 싸다. 앱 전체에 레이트 리밋이 0건인 것은 **별개의 남은 구멍**이다
  (`nexttodo.md` 인프라).
- **토큰 유출이 실질 위험**이다. `JWT_SECRET`과 같은 등급으로 다룬다. 유출 시 재발급은
  1단계 명령을 다시 돌리고 2단계 작업의 헤더를 갱신하면 된다(`gcloud scheduler jobs
  update http outlook-refresh --update-headers ...`).

Cloud Armor 레이트 리밋은 지금 `run.app` 직결이라 LB부터 세워야 하고, 앱 레벨
인메모리 리밋은 Cloud Run 다중 인스턴스에서 카운터가 갈려 실효가 약하다 — 현재
규모에선 과하다고 판단했다.
