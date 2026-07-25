"""통합 전/후 시군구 법정동코드 대응표 생성 (docs/seed/legacy_sgg_code.csv).

행정통합(전남광주통합특별시)으로 시군구 코드가 재부여됐는데 흙토람은 아직 옛 코드로만
데이터를 갖고 있다(검정 기록이 통합 전 시점 자료). 그래서 조회 시 옛 코드로 재시도해야 한다.

기존에도 같은 문제를 겪었지만(scripts/retry_merged_region_soil_profile.py) 대응표를 남기지
않아 매번 병합 전 CSV를 다시 구해야 했다. 이번엔 시드로 영구 저장한다.

대응 규칙(그때 검증된 것): 통합으로 **앞 5자리(시도2+시군구3)만 바뀌고 읍면동 이하 5자리는
그대로**다. 예) 목포시 용당동 신 12110-010100 / 구 46110-010100. 그래서 읍면동명으로 매칭해
앞 5자리 대응만 뽑아내면 된다.

사용법: python scripts/gen_legacy_bjd_map.py <병합전_법정동코드_CSV>
    예: python scripts/gen_legacy_bjd_map.py 20250415.csv
"""

import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "docs" / "seed"
CURRENT_CSV = SEED_DIR / "bjd_to_region.csv"
OUT_CSV = SEED_DIR / "legacy_sgg_code.csv"

# 코드가 재부여된 시/도. 이 범위로 한정하지 않으면 '중구·동구·북구'처럼 여러 광역시에
# 같은 이름이 있는 구가 엉뚱하게 매칭된다(예: 대구 중구 → 서울 중구, 매칭 1~2건).
# 통합이 또 생기면 여기에 추가한다.
MERGED_SIDO = {"전남광주통합특별시"}

# 다수결 최소 지지 비율. 아래면 대응이 불확실하다고 보고 [확인 필요]로 보고한다.
MIN_VOTE_SHARE = 0.8


def _read_legacy(path: Path) -> dict[tuple[str, str], str]:
    """병합 전 CSV → {(시군구명, 읍면동명): 앞5자리}. 삭제된 행은 제외한다."""
    out: dict[tuple[str, str], str] = {}
    with path.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            code = (r.get("법정동코드") or "").strip()
            sgg = (r.get("시군구명") or "").strip()
            emd = (r.get("읍면동명") or "").strip()
            ri = (r.get("리명") or "").strip()
            deleted = (r.get("삭제일자") or "").strip()
            if deleted or ri or not (sgg and emd) or len(code) != 10:
                continue
            out.setdefault((sgg, emd), code[:5])
    return out


def main() -> None:
    if len(sys.argv) != 2:
        print("사용법: python scripts/gen_legacy_bjd_map.py <병합전_법정동코드_CSV>")
        raise SystemExit(1)

    legacy = _read_legacy(Path(sys.argv[1]))

    # 현재 코드에서 (시군구명, 읍면동명)로 옛 앞5자리를 찾아 신→구 앞5자리 대응을 투표로 정한다.
    # 동명이 여러 시군구에 있을 수 있어 읍면동명까지 묶어 매칭하고, 다수결로 흔들림을 없앤다.
    votes: dict[tuple[str, str], Counter[str]] = {}
    with CURRENT_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["ri"] or not r["eupmyeondong"]:
                continue
            if r["sido"] not in MERGED_SIDO:
                continue  # 통합 대상 아님 — 동명 구(區) 오탐 방지
            old_prefix = legacy.get((r["region_name"], r["eupmyeondong"]))
            if old_prefix is None:
                continue
            new_prefix = r["bjd_code"][:5]
            if old_prefix == new_prefix:
                continue  # 통합 영향 없는 지역
            votes.setdefault((r["sido"], r["region_name"]), Counter())[
                f"{new_prefix}>{old_prefix}"
            ] += 1

    rows: list[dict[str, str]] = []
    for (sido, region_name), counter in sorted(votes.items()):
        pair, n = counter.most_common(1)[0]
        new_prefix, old_prefix = pair.split(">")
        share = n / sum(counter.values())
        rows.append(
            {
                "sido": sido,
                "region_name": region_name,
                "new_sgg_prefix": new_prefix,
                "legacy_sgg_prefix": old_prefix,
                "matched_districts": str(n),
                "vote_share": f"{share:.2f}",
                "ambiguous": "true" if share < MIN_VOTE_SHARE else "false",
            }
        )

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "sido", "region_name", "new_sgg_prefix",
                "legacy_sgg_prefix", "matched_districts", "vote_share", "ambiguous",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    ambiguous = [r for r in rows if r["ambiguous"] == "true"]
    print(f"대응표 {len(rows)}건 -> {OUT_CSV.relative_to(ROOT)}")
    if ambiguous:
        print(f"[확인 필요] 다수결로 정한 모호 건 {len(ambiguous)}개: "
              f"{[r['region_name'] for r in ambiguous]}")


if __name__ == "__main__":
    main()
