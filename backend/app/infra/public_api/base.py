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


def fetch_items(
    url: str,
    params: dict[str, str],
    timeout: float = 10.0,
    code_tag: str = "Result_Code",
    msg_tag: str = "Result_Msg",
    success: str = "200",
) -> list[dict[str, str | None]]:
    """공공데이터포털 XML 응답(header.{code_tag} + body.items.item*)을 dict 리스트로 변환.

    기본값(Result_Code/Result_Msg, 성공="200")은 흙토람 SoilEnviron 계열 API에서 실제
    확인한 값(토양특성 단면정보·토양검정 화학성 API 기술명세서). 다른 제공기관 API는
    관례가 다를 수 있어 code_tag/msg_tag/success로 오버라이드한다.
    """
    resp = httpx.get(url, params=params, timeout=timeout)
    resp.raise_for_status()

    xml_text = resp.text
    if xml_text.lstrip().startswith("<?xml"):
        # 실제 흙토람 응답은 standalone="true"로 XML 선언이 스펙 위반(정상값은 yes/no)이라
        # ElementTree가 파싱을 거부한다 — 선언부는 필요 없으니 통째로 잘라낸다.
        xml_text = xml_text.split("?>", 1)[1]
    root = ElementTree.fromstring(xml_text)

    result_code = root.findtext(f".//header/{code_tag}")
    if result_code != success:
        result_msg = root.findtext(f".//header/{msg_tag}") or "알 수 없는 오류"
        raise PublicApiError(result_code or "UNKNOWN", result_msg)

    return [{child.tag: child.text for child in item} for item in root.findall(".//body/items/item")]
