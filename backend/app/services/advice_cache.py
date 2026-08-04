"""추천 문구 캐시가 낡았는지 판정하는 지문 — 단기·장기 공용.

**문제**: 두 추천 모두 "언제 다시 만들어야 하나"를 날짜로 판정하고 있었고, 둘 다 그것으로는
부족했다.

- 단기(`daily_recommendation`)는 `(밭, 날짜)`가 키였다. 그런데 기상청 단기예보는 발표 주기가
  3시간이라 하루에 여덟 번 갱신된다(`short_term_service.get_forecast_rows`). 새벽 조회에서
  "위험 신호가 없습니다"를 저장하면 오후 발표에 폭우가 들어와도 그 문구가 그대로 나간다 —
  **같은 화면에서** 날짜 카드는 강수 경고를 띄우는데 추천은 위험이 없다고 말한다.
- 장기(`long_term_recommendation`)는 창이 달 단위라 자연 키가 아예 없었다. 매월 23일
  3개월전망 발표로 점수가 갈아엎어져도 문구만 낡은 채 남는다.

둘 다 **에러 없이 조용히 거짓말**하는 부류라 §18-4에 걸린다.

**해법**: 다듬은 문구를 결정하는 것이 정확히 무엇인지 보면 답이 나온다. 두 서비스 모두
`polish()`가 `build_prompt(crop_name, base_text)` 하나를 LLM에 넘긴다. 즉 결과를 바꾸는 것은

    프롬프트 버전  +  작물명  +  규칙 문구(base_text)

**이 셋뿐이고, 이 셋이 전부다.** 그래서 이것만 해시한다.

**왜 점수·등급을 넣지 않나**: 문구에 한 글자도 안 들어가기 때문이다. 장기 히트맵 점수가
80.0 → 79.9로 바뀌어도 문장은 같다 — 넣으면 낡지는 않지만 LLM을 헛되이 다시 부른다.
반대로 규칙 문구가 바뀌면 지문은 반드시 바뀐다(문구 자체를 해시하므로). 즉 이 지문은
**필요충분**하다: 문장이 달라질 때만, 그리고 달라지면 반드시 재생성된다.

`PROMPT_VERSION`을 넣는 이유는 프롬프트를 고쳤는데 캐시 때문에 반영이 안 되는 함정을
막기 위해서다 — 버전을 올리면 저장된 문구가 전량 재생성된다.
"""

import hashlib
import json


def prompt_fingerprint(prompt_version: str, crop_name: str, base_text: str) -> str:
    """LLM 프롬프트를 결정하는 전부의 sha256 hex. 결정론 필수(§2) — 같은 입력이면 같은 지문.

    JSON으로 감싸는 이유는 구분자 없이 이어 붙이면 경계가 모호해지기 때문이다
    (`("a", "bc")`와 `("ab", "c")`가 같은 문자열이 된다).
    """
    raw = json.dumps(
        {"v": prompt_version, "crop": crop_name, "base": base_text},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
