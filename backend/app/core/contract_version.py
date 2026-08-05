"""FarmML 이관 계약(`outcomes/`)의 배포 코드측 버전 기록(finalplan.md P5 작업3).

왜 문자열 리터럴로 박아두는가: 런타임에 `outcomes/VERSIONS.json`을 읽지 않는다. 그 파일이
바뀌어도 이 상수가 조용히 따라가면 안 된다 — 배포 코드가 실제로 어떤 계약 버전의 값을
서빙하는지는 사람이 데이터(밴드·마이그레이션)를 그 버전에 맞춰 갱신한 시점에만 여기를
같이 갱신해야 확정된다(`outcomes/README.md` 적용 체크리스트 8번).

값 출처: `outcomes/VERSIONS.json`의 `knowledge_version`/`scoring_version` 실값(2026-08-05
확인). `tests/test_farmml_contract.py`가 이 상수와 대장 값을 대조한다 — 어긋나면 배포 코드가
다른 계약 버전을 서빙한다는 뜻이라 실패해야 한다.

이 상수를 응답에 싣거나 다른 코드에서 참조하지 않는다 — 지금은 기록·검증 목적뿐이다(YAGNI).
"""

KNOWLEDGE_VERSION = "2026-08-05-v6"
SCORING_VERSION = "2026-08-05-v6"
