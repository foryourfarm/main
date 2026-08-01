"""`.env.example`의 키 이름이 실제로 읽히는지 검증 (CLAUDE.md §17).

**왜 필요한가**: `config.py`는 `extra="ignore"`라 선언되지 않은 이름을 넣으면 **에러 없이**
기본값(보통 빈 문자열)이 된다. 그래서 이름이 어긋나면 배포도 성공하고 앱도 뜨는데 그 API만
조용히 죽는다. 이 부류가 이미 세 번 반복됐다:

1. `WEATHER_API_KEY`/`SOIL_API_KEY` — 팀원 로컬에서 회원가입·밭 등록이 실패했다.
2. `VWORLD_API` vs 필드 `vworld_apikey` — `.env.example`이 계속 안 읽히는 이름을 안내했다.
3. `weather_data_APIkey` vs 필드 `weather_apihub_key` — 실제 apihub 키가 클라이언트가 읽지
   않는 필드에 들어가 있었다.

`config.py`와 `.env.example` 양쪽에 "바꾸면 같이 고쳐라"는 주석이 있었고 심지어 "이런 불일치가
다시 생기면 §17 검증 테스트가 잡는다"고 적혀 있었지만 **그 테스트가 없었다.** 규칙만 있고
강제 장치가 없어서 3번이 또 생겼다. 이 파일이 그 장치다.

alias(`validation_alias`)로 받는 이름도 통과시킨다 — 과거 이름 호환을 남기는 것은 정상이다.
"""

import re
import unittest
from pathlib import Path

from pydantic import AliasChoices

from app.core.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"

# `KEY=value` / `KEY = value` / 주석 처리된 `# KEY=value`(선택 항목) 전부 잡는다.
# 선택 항목도 이름이 틀리면 주석을 풀었을 때 조용히 무시되므로 같이 검증해야 한다.
#
# **이름 조건이 느슨하면 산문을 키로 오인한다.** 처음엔 `[A-Za-z_]\w*=`로 잡았다가 주석에 있는
# `# SameSite=Lax는 …` 설명 문장을 키로 읽어 오탐이 났다. 이 파일의 실제 키는 전부 밑줄이
# 들어간 대문자 이름(`DATABASE_URL`, `VWORLD_APIkey`, `COOKIE_SAMESITE` …)이라 그걸 요구한다.
# 밑줄 없는 한 단어 키를 새로 추가하면 이 검사에서 빠진다(오탐 대신 누락을 택했다 — 오탐은
# 테스트를 못 믿게 만들지만 누락은 기존 키 검증을 해치지 않는다). 그런 키를 추가하면 여기도 고칠 것.
_KEY_LINE = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9]*(?:_[A-Za-z0-9]+)+)\s*=")


def _readable_names() -> set[str]:
    """Settings가 실제로 읽어들이는 env 이름 전부(소문자). 필드명 + alias."""
    names: set[str] = set()
    for field_name, field in Settings.model_fields.items():
        names.add(field_name.lower())
        alias = field.validation_alias
        if isinstance(alias, AliasChoices):
            names.update(str(a).lower() for a in alias.choices)
        elif isinstance(alias, str):
            names.add(alias.lower())
    return names


def _example_keys() -> list[str]:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    out: list[str] = []
    for line in text.splitlines():
        m = _KEY_LINE.match(line)
        if m:
            out.append(m.group(1))
    return out


class TestEnvExampleMatchesSettings(unittest.TestCase):
    def test_example_file_exists(self):
        # 없으면 아래 검증이 전부 공허하게 통과한다(빈 목록은 항상 참).
        self.assertTrue(ENV_EXAMPLE.is_file(), f"{ENV_EXAMPLE} 가 없다")

    def test_every_example_key_is_readable(self):
        readable = _readable_names()
        unreadable = [k for k in _example_keys() if k.lower() not in readable]
        self.assertEqual(
            unreadable,
            [],
            f".env.example의 이 키들은 Settings가 읽지 않는다(조용히 빈 값이 된다): {unreadable}. "
            "config.py에 필드를 추가하거나 이름을 맞출 것.",
        )

    def test_finds_keys_at_all(self):
        # 정규식이 깨지면 키를 0개로 읽고 위 검증이 무의미해진다.
        self.assertGreater(len(_example_keys()), 5)

    def test_detects_a_known_bad_name(self):
        # 이 테스트 자체가 헛돌지 않는지 — 과거에 실제로 문제였던 이름은 읽히지 않아야 한다.
        readable = _readable_names()
        self.assertNotIn("weather_api_key", readable)  # 팀원이 겪은 이름
        self.assertNotIn("soil_api_key", readable)
        self.assertNotIn("vworld_api", readable)  # `key` 접미사 없는 이름

    def test_apihub_key_reachable_by_both_names(self):
        # 정본 이름과 과거 이름 둘 다 읽혀야 한다(실제 키가 과거 이름으로 들어와 있다).
        readable = _readable_names()
        self.assertIn("weather_apihub_key", readable)
        self.assertIn("weather_data_apikey", readable)


if __name__ == "__main__":
    unittest.main()
