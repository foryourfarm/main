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

남은 1,120건은 코드 규칙으로 못 푼다. 구(區) 신설·시군 재편 때는 **읍면동·리 코드까지
재부여**돼 "앞 5자리만 바뀐다"는 전제가 깨지기 때문이다(화성시 효행구는 접미사 매칭이
30%였다). 그래서 `augment_by_name()`이 이름으로 이어 붙여 **99.1%**까지 올린다.
"""

import binascii
import csv
import struct
from collections import Counter
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


def load_centroids(
    path: Path, code_suffix: str = ""
) -> tuple[dict[str, tuple[float, float]], dict[str, str]]:
    """법정구역 CSV → ({법정동코드: (위도, 경도)}, {법정동코드: 이름}).

    이름을 함께 주는 이유: 구(區) 신설로 코드가 통째로 재부여된 구역은 코드로 못 찾고
    이름으로만 이어 붙일 수 있다(`augment_by_name`).

    Args:
        path: LP_AA_RI.csv 또는 LP_AA_EMD.csv
        code_suffix: 코드에 덧붙일 문자열. 읍면동 데이터셋은 8자리라 "00"이 필요하다.

    섬처럼 조각이 여러 개면 **가장 큰 조각**의 중심을 쓴다 — 조각 전체를 평균하면
    바다 위로 갈 수 있다.
    """
    out: dict[str, tuple[float, float]] = {}
    labels: dict[str, str] = {}
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
            code = parts[1].strip() + code_suffix
            out[code] = (round(best[1], 6), round(best[0], 6))
            labels[code] = parts[2].strip()
    return out, labels


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


# 이름 매칭으로 이어 붙일 때 시군구 대응을 인정할 최소 득표율. 실측에서 성립하는 대응은
# 87~100%로 몰려 있고 그 아래는 우연히 겹친 동명이 리다(잡음은 10% 미만에 흩어진다).
NAME_VOTE_MIN_SHARE = 0.7
NAME_VOTE_MIN_COUNT = 3


def augment_by_name(
    rows: list[tuple[str, str]],
    centroids: dict[str, tuple[float, float]],
    names: dict[str, str],
    legacy: dict[str, str],
) -> dict[str, tuple[float, float]]:
    """코드로 못 찾은 행을 **이름**으로 이어 붙인다. {현행 bjd_code: 좌표}.

    왜 코드만으로 부족한가: 구(區) 신설처럼 시군구가 쪼개질 때는 **읍면동·리 코드까지
    재부여**돼서 `resolve()`가 기대는 "앞 5자리만 바뀌고 뒤는 그대로" 규칙이 깨진다.
    실측으로 확인했다 — 화성시 효행구는 접미사 매칭이 30%에 그쳤다.

    그래서 두 단계로 간다:
      1. 시군구 대응을 **이름 득표**로 정한다. 그 시군구의 리 이름들이 어느 옛 시군구에
         가장 많이 들어 있는지 센다(접미사를 보지 않으므로 코드 재부여에 영향받지 않는다).
         실측 득표율: 여주시→여주군 98%, 청주 4개 구→청원군 98~100%, 군위군→경북 군위 100%.
      2. 그 시군구 안에서 이름이 **유일하게** 일치하는 것만 취한다. 같은 시군구에 같은
         이름의 리가 둘 이상이면 어느 쪽인지 알 수 없으므로 **버린다** — 찍어서 맞히면
         엉뚱한 골짜기 고도가 들어가고, 그건 폴백보다 나쁘다(§18-4).

    Args:
        rows: (현행 bjd_code, 말단 이름). 리면 리명, 읍면동이면 읍면동명.
    """
    unresolved = [
        (code, name) for code, name in rows if resolve(code, centroids, legacy) is None
    ]
    if not unresolved:
        return {}

    by_sgg: dict[str, dict[str, list[str]]] = {}
    for code, name in names.items():
        by_sgg.setdefault(code[:5], {}).setdefault(name, []).append(code)

    # 1단계: 신 시군구 접두 → 옛 접두 (이름 득표)
    votes: dict[str, Counter[str]] = {}
    totals: Counter[str] = Counter()
    for code, name in unresolved:
        totals[code[:5]] += 1
        bucket = votes.setdefault(code[:5], Counter())
        for sgg, names_here in by_sgg.items():
            if name in names_here:
                bucket[sgg] += 1

    sgg_map: dict[str, str] = {}
    for prefix, counter in votes.items():
        if not counter:
            continue
        old, hits = counter.most_common(1)[0]
        if hits >= NAME_VOTE_MIN_COUNT and hits / totals[prefix] >= NAME_VOTE_MIN_SHARE:
            sgg_map[prefix] = old

    # 2단계: 그 시군구 안에서 이름이 유일한 것만
    out: dict[str, tuple[float, float]] = {}
    for code, name in unresolved:
        old = sgg_map.get(code[:5])
        if old is None:
            continue
        candidates = by_sgg.get(old, {}).get(name, [])
        if len(candidates) == 1 and candidates[0] in centroids:
            out[code] = centroids[candidates[0]]
    return out
