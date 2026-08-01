"""법정구역 폴리곤 CSV(국토지리정보원 공간정보공동활용) → 법정동코드별 대표점.

`gen_altitude_seed.py`가 쓰는 좌표 소스 중 하나다. 데이터셋 두 개가 같은 포맷이라 한 곳에 둔다.

    LP_AA_RI.csv    리      15,298건  리코드 10자리
    LP_AA_EMD.csv   읍면동   5,026건  읍면동코드 **8자리**(뒤에 "00"을 붙여야 우리 10자리와 맞는다)

받는 곳(둘 다 이용허락범위 제한 없음·로그인 없이 직접 다운로드, 2023-09-15 기준):
    https://www.data.go.kr/data/15123130/fileData.do   리
    https://www.data.go.kr/data/15123128/fileData.do   읍면동

**의존성이 없다.** 좌표가 이미 WGS84 경위도라 좌표변환이 필요 없고, WKB는 `struct`로 읽는다
(GDAL/shapely 불필요). 인코딩은 EUC-KR(cp949)이다.

원본 292MB는 리포에 커밋하지 않는다 — 격자 엑셀과 같은 처리로 **산출 CSV만** 남긴다
(`gen_region_grid_seed.py` 참고).

**코드 지연 주의**: 데이터셋이 2023-09 기준이라 그 뒤의 행정구역 개편이 반영돼 있지 않다.
`resolve()`가 세 단계로 되짚는다 — 직접 → 통합 전 시군구 코드(`legacy_sgg_code.csv`) →
시도 재부여(강원 51↔42, 전북 52↔45). 이 셋으로 리 15,209건 중 92.6%가 붙는다.
남은 1,120건(화성시 구 신설·청주시 구 재편·군위군 대구 편입 등)은 상위 단위로 폴백한다.
"""

import binascii
import csv
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGACY_SGG = ROOT / "docs" / "seed" / "legacy_sgg_code.csv"

# 시도 재부여 대응(신 → 구). 특별자치도 전환으로 시도 코드가 바뀌었고 나머지 8자리는 그대로다.
# 실측으로 확인했다 — 이 대응 하나로 리 2,562건이 추가로 붙는다.
LEGACY_SIDO = {"51": "42", "52": "45"}  # 강원특별자치도, 전북특별자치도


def _exterior_rings(wkb_hex: str) -> list[list[tuple[float, float]]]:
    """WKB (Multi)Polygon → 조각별 외곽링 좌표열.

    내부 링(구멍)은 버린다 — 대표점 위치에 주는 영향이 작고, 우리는 면적이 아니라
    한 점만 필요하다.
    """
    raw = binascii.unhexlify(wkb_hex)
    order = "<" if raw[0] == 1 else ">"
    geom_type = struct.unpack_from(order + "I", raw, 1)[0]
    offset = 5

    n_polygons = 1
    if geom_type == 6:  # MultiPolygon
        n_polygons = struct.unpack_from(order + "I", raw, offset)[0]
        offset += 4

    out: list[list[tuple[float, float]]] = []
    for _ in range(n_polygons):
        if geom_type == 6:
            offset += 5  # 조각마다 붙는 byte order(1) + geometry type(4)
        n_rings = struct.unpack_from(order + "I", raw, offset)[0]
        offset += 4
        for ring_index in range(n_rings):
            n_points = struct.unpack_from(order + "I", raw, offset)[0]
            offset += 4
            coords = struct.unpack_from(order + f"{n_points * 2}d", raw, offset)
            offset += n_points * 16
            if ring_index == 0:
                out.append(
                    [(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]
                )
    return out


def _centroid(ring: list[tuple[float, float]]) -> tuple[float, float, float]:
    """다각형 무게중심(신발끈 공식) + 면적. (x, y, |면적|).

    정점 단순평균이 아니다 — 그건 해안선처럼 정점이 촘촘한 쪽으로 끌린다.
    """
    area = cx = cy = 0.0
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if area == 0:  # 퇴화 폴리곤(면적 0) — 평균으로 대체한다
        return sum(p[0] for p in ring) / n, sum(p[1] for p in ring) / n, 0.0
    area *= 0.5
    return cx / (6 * area), cy / (6 * area), abs(area)


def load_centroids(path: Path, code_suffix: str = "") -> dict[str, tuple[float, float]]:
    """법정구역 CSV → {법정동코드: (위도, 경도)}.

    Args:
        path: LP_AA_RI.csv 또는 LP_AA_EMD.csv
        code_suffix: 코드에 덧붙일 문자열. 읍면동 데이터셋은 8자리라 "00"이 필요하다.

    섬처럼 조각이 여러 개면 **가장 큰 조각**의 중심을 쓴다 — 조각 전체를 평균하면
    바다 위로 갈 수 있다.
    """
    out: dict[str, tuple[float, float]] = {}
    with path.open("rb") as f:
        f.readline()  # 헤더
        for line in f:
            parts = line.decode("cp949").rstrip("\n").split(",")
            if len(parts) < 6 or not parts[1].strip():
                continue
            try:
                rings = _exterior_rings(parts[5].strip())
            except (binascii.Error, struct.error, ValueError):
                continue  # 손상된 도형 한 건이 전체 적재를 죽이지 않게 한다(§12)
            if not rings:
                continue
            best = max((_centroid(r) for r in rings), key=lambda t: t[2])
            out[parts[1].strip() + code_suffix] = (round(best[1], 6), round(best[0], 6))
    return out


def legacy_sgg_map() -> dict[str, str]:
    """신 시군구 5자리 → 통합 전 5자리 (`docs/seed/legacy_sgg_code.csv`)."""
    if not LEGACY_SGG.exists():
        return {}
    return {
        row["new_sgg_prefix"]: row["legacy_sgg_prefix"]
        for row in csv.DictReader(LEGACY_SGG.open(encoding="utf-8"))
    }


def resolve(
    bjd_code: str, centroids: dict[str, tuple[float, float]], legacy: dict[str, str]
) -> tuple[float, float] | None:
    """현행 법정동코드로 2023년 기준 폴리곤을 찾는다. 코드 지연을 세 단계로 되짚는다."""
    if bjd_code in centroids:
        return centroids[bjd_code]

    merged = legacy.get(bjd_code[:5])
    if merged and merged + bjd_code[5:] in centroids:
        return centroids[merged + bjd_code[5:]]

    sido = LEGACY_SIDO.get(bjd_code[:2])
    if sido and sido + bjd_code[2:] in centroids:
        return centroids[sido + bjd_code[2:]]

    return None
