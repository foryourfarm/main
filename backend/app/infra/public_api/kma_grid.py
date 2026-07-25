"""위경도 → 기상청 단기예보 격자(nx, ny) 변환 (Lambert Conformal Conic).

기상청 단기예보 API는 격자좌표만 받는다(위경도 불가). 기상청이 배포하는 행정구역↔격자
엑셀은 data.go.kr 참고문서 zip 안에 있어 자동 취득이 어려우므로, 공식 투영 파라미터로
직접 변환한다.

파라미터는 기상청 활용가이드에 공개된 값이며, 구현이 맞는지는 널리 공개된 기준값
(서울시청 → 60,127 / 부산시청 → 98,76 등)으로 테스트에서 검증한다 — 추측이 아니라
검증된 표준 변환이다(CLAUDE.md §3-4).

전국 5km 격자: 동서 149 × 남북 253.
"""

import math

RE = 6371.00877  # 지구 반경(km)
GRID = 5.0  # 격자 간격(km)
SLAT1 = 30.0  # 표준 위도 1
SLAT2 = 60.0  # 표준 위도 2
OLON = 126.0  # 기준점 경도
OLAT = 38.0  # 기준점 위도
XO = 43  # 기준점 격자 X
YO = 136  # 기준점 격자 Y

GRID_NX_MAX = 149
GRID_NY_MAX = 253

_DEGRAD = math.pi / 180.0


def latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """(위도, 경도) → (nx, ny). 격자 범위를 벗어나면 ValueError.

    범위 검사를 두는 이유: 잘못된 좌표(0,0 등)가 조용히 유효한 격자로 둔갑해 엉뚱한
    지역 예보를 가져오는 것을 막는다(§12 경계 방어).
    """
    re = RE / GRID
    slat1 = SLAT1 * _DEGRAD
    slat2 = SLAT2 * _DEGRAD
    olon = OLON * _DEGRAD
    olat = OLAT * _DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = sf**sn * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / ro**sn

    ra = math.tan(math.pi * 0.25 + lat * _DEGRAD * 0.5)
    ra = re * sf / ra**sn
    theta = lon * _DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = int(ra * math.sin(theta) + XO + 0.5)
    ny = int(ro - ra * math.cos(theta) + YO + 0.5)

    if not (1 <= nx <= GRID_NX_MAX and 1 <= ny <= GRID_NY_MAX):
        raise ValueError(f"격자 범위 밖: lat={lat}, lon={lon} → nx={nx}, ny={ny}")
    return nx, ny
