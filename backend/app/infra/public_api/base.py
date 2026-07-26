"""data.go.kr류 공공 XML API 공통 처리 (CLAUDE.md §12).

요청 -> XML 파싱 -> resultCode 체크까지만 여기서 하고, 필드별 검증(pydantic)과
캐시 upsert는 호출부(API별 클라이언트)에서 한다 — API마다 응답 스키마가 다르므로.
"""

from xml.etree import ElementTree

import httpx


class PublicApiError(Exception):
    """resultCode != '00' (공공데이터포털 표준 에러코드)."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"[{code}] {message}")


def _header_text(root: ElementTree.Element, tag: str) -> str | None:
    """header 안에서 태그를 **대소문자 무시**로 찾는다.

    왜 무시하는가: 같은 data.go.kr 안에서도 제공기관마다 케이스가 다르다 —
    토양특성 단면정보·토양검정 화학성은 `Result_Code`, 농경지화학성 통계 V2와 농업기상
    V3은 `result_Code`다(각 기술명세서 확인 + 실제 응답 확인). ElementTree는 대소문자를
    구분하므로 케이스가 하나만 어긋나면 **성공 응답이 전부 에러로 둔갑한다** — 실제로
    농경지화학성 클라이언트가 모든 호출에서 `[UNKNOWN] 알 수 없는 오류`를 던지고 있었다.
    호출부마다 케이스를 외우게 하는 대신 여기서 한 번에 흡수한다.
    """
    want = tag.lower()
    for header in root.iter():
        if header.tag.lower() != "header":
            continue
        for child in header:
            if child.tag.lower() == want:
                return child.text
    return None


def fetch_items(
    url: str,
    params: dict[str, str],
    timeout: float = 10.0,
    code_tag: str = "Result_Code",
    msg_tag: str = "Result_Msg",
    success: str = "200",
) -> list[dict[str, str | None]]:
    """공공데이터포털 XML 응답(header.{code_tag} + body.items.item*)을 dict 리스트로 변환.

    code_tag/msg_tag는 대소문자를 구분하지 않는다(`_header_text` 참고). success 코드가
    다른 제공기관(예: 성공="00")은 success로 오버라이드한다.
    """
    resp = httpx.get(url, params=params, timeout=timeout)
    resp.raise_for_status()

    xml_text = resp.text
    if xml_text.lstrip().startswith("<?xml"):
        # 실제 흙토람 응답은 standalone="true"로 XML 선언이 스펙 위반(정상값은 yes/no)이라
        # ElementTree가 파싱을 거부한다 — 선언부는 필요 없으니 통째로 잘라낸다.
        xml_text = xml_text.split("?>", 1)[1]
    root = ElementTree.fromstring(xml_text)

    result_code = _header_text(root, code_tag)
    if result_code != success:
        result_msg = _header_text(root, msg_tag) or "알 수 없는 오류"
        raise PublicApiError(result_code or "UNKNOWN", result_msg)

    return [{child.tag: child.text for child in item} for item in root.findall(".//body/items/item")]
