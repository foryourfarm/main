# docs/ — 문서 인덱스

프로젝트 문서 모음. 루트에는 최상위 규범 문서(`CLAUDE.md`, `PRD.md`, `DB.md`, `README.md`, `nexttodo.md`)만 두고, 나머지 설계·데이터·참고 자료는 여기 폴더별로 정리한다.

## 폴더 구조

| 경로 | 내용 |
|---|---|
| `docs/main-logic-guide.md` | **메인 로직 백엔드 구현 가이드(팀원용)** — 토양변화 추론·적합도 룰·수집. 근거는 `ml/backend_ml_handoff.md`. |
| `docs/crop-domain-knowledge.md` | 작물 생육 기준값(적정/허용 범위) 문헌 근거 — 논문 13편에서 추출. `0004_crop_growth_guide_seed.py`가 인용. |
| `docs/auth-security.md` | 인증·보안 설계(분리 토큰 JWT) FE 연동 계약. |
| `docs/llm-integration.md` | LLM/챗봇 연동 계약(SSE, 폴백, 프롬프트 가드레일 §11). |
| `docs/llm-benchmark-eval.md` | 로컬 LLM 벤치마크·평가 기록. |
| `docs/ml/` | 머신러닝 산출물·결정 기록(`backend_ml_handoff.md` = 백엔드 인계 최종). `aws-solar-climatology-explainer.md` = PR #68·#69(AWS 평년치·일사량 도너) 팀원용 설명 — 선택 근거·실험 과정·재현 스크립트. |
| `docs/seed/` | 생육 지침 시드 데이터(작물별). |
| `docs/design/` | UI/UX 가이드라인·시안(Correction 초안, UI-UX-Guideline 01~03, Anti-UI-UX, 서비스 특강). |
| `docs/data/` | 데이터 가이드·전처리·리포트, 흙토람 API/데이터셋/법정동코드 정리. |
| `docs/api-specs/` | 공공데이터 OpenAPI 스펙 PDF(토양·기상·작물·비료 등). |

## 정리 이력

- **2026-07-24 루트 정리**: 루트에 흩어져 있던 설계·데이터 md와 공공 API PDF들을 `git mv`(이력 보존)로 `docs/design`·`docs/data`·`docs/api-specs`로 이동. 루트는 규범 문서만 남김. 코드/문서의 하드 경로 참조는 없어 링크 손상 없음(참조는 파일명 기반 주석·같은 폴더 위키링크뿐).
- **2026-07-24 crop-domain-knowledge.md 추가**: 루트에 있던 작물 생육 논문 14편(오이4·배4·감자2·상추3·사과1)에서 정량 수치를 추출해 문서화. 기존 `crop_growth_guide` 시드값 다수가 이번 조사로 검증되지 않아 `[확인 필요]` 항목으로 남김(원본 논문 PDF 14개는 루트에 그대로 있음, 이후 정리 필요). 사과 논문(P14)은 근권 토양온도 다루는 논문이라 기존 시드의 단계별 대기온도 값은 여전히 미검증.
