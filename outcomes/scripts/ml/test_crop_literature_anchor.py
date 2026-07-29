"""Regression test for crop-literature-anchor scoring pipeline changes.

Tests:
1. Import CROP_ANCHORS from scripts/ml/crop_literature_anchor_experiment.py.
2. Assert "09001" and "09011" present in CROP_ANCHORS.
3. Assert apple and pear have explicit temperature anchors.
4. Assert non-empty documented_rules with sourced leaf range dicts.
5. Assert existing crops ("07001", "03001", "04009") present with dict temp guides.
6. Load memory/approved-region-score-rules.json and assert "note" containing "확인 필요".
7. Scan rules JSON and experiment script for forbidden accuracy/causal/yield prediction claims.
8. Validate data/ml/crop_literature_anchor_experiment.csv, AnswerData.csv, RegionalScore.csv.
"""
import json
import sys
from pathlib import Path

import pandas as pd

# 1. Path setup matching scripts/ml execution convention
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ML = ROOT / "scripts" / "ml"
if str(SCRIPTS_ML) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ML))

from crop_literature_anchor_experiment import CROP_ANCHORS


def test_crop_anchors_new_entries():
    crop_names = ("apple", "pear", "lettuce", "potato", "cucumber")
    missing_anchor_files = [
        name for name in crop_names
        if not (SCRIPTS_ML / "crop_anchors" / f"{name}.py").exists()
    ]
    assert not missing_anchor_files, f"Missing crop anchor files: {missing_anchor_files}"

    # 2. Assert "09001" and "09011" are present in CROP_ANCHORS
    assert "09001" in CROP_ANCHORS, "'09001' (사과) missing from CROP_ANCHORS"
    assert "09011" in CROP_ANCHORS, "'09011' (배) missing from CROP_ANCHORS"

    # 3. Apple and pear use official suitable/possible growing-temperature bands.
    apple_temp = CROP_ANCHORS["09001"]["temp"]
    assert apple_temp["months"] == [4, 5, 6, 7, 8, 9, 10]
    assert (apple_temp["optimal_min"], apple_temp["optimal_max"], apple_temp["allowed_min"], apple_temp["allowed_max"]) == (14.5, 18.5, 13.5, 19.5)
    assert "농업·농촌 기후정보시스템" in apple_temp["source"]
    pear_temp = CROP_ANCHORS["09011"]["temp"]
    assert pear_temp["months"] == [4, 5, 6, 7, 8, 9, 10]
    assert (pear_temp["optimal_min"], pear_temp["optimal_max"], pear_temp["allowed_min"], pear_temp["allowed_max"]) == (18.5, 21.5, 17.0, 23.0)
    assert "농업·농촌 기후정보시스템" in pear_temp["source"]

    # 4. Assert non-empty documented_rules and all leaf range dicts have a valid "source" key
    def check_sources(node, path="documented_rules"):
        if isinstance(node, dict):
            range_keys = {"optimal_min", "optimal_max", "allowed_min", "allowed_max", "min", "max", "optimal", "indicator"}
            if any(k in node for k in range_keys):
                assert "source" in node, f"Missing 'source' key at {path}"
                assert isinstance(node["source"], str), f"'source' at {path} must be str"
                assert len(node["source"].strip()) > 0, f"'source' at {path} must be non-empty"
            else:
                for k, v in node.items():
                    check_sources(v, f"{path}.{k}")
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                check_sources(item, f"{path}[{idx}]")

    for crop_id in ("09001", "09011"):
        doc_rules = CROP_ANCHORS[crop_id].get("documented_rules")
        assert isinstance(doc_rules, dict) and len(doc_rules) > 0, f"{crop_id} must have non-empty documented_rules"
        check_sources(doc_rules, f"CROP_ANCHORS['{crop_id}']['documented_rules']")
    pear_temp = CROP_ANCHORS["09011"]["documented_rules"]["growing_temp"]
    assert pear_temp["months"] == [4, 5, 6, 7, 8, 9, 10] and pear_temp["target"] == 20.0, (
        "배 농진청 생육기(4~10월)·목표기온(20℃) 보존 실패"
    )

    # 5. Assert existing 3 crops are present with unchanged temp shape (dicts, not None)
    for crop_id in ("07001", "03001", "04009"):
        assert crop_id in CROP_ANCHORS, f"Existing crop {crop_id} missing from CROP_ANCHORS"
        assert isinstance(CROP_ANCHORS[crop_id]["temp"], dict), f"Existing crop {crop_id} temp shape changed"


def test_approved_rules_json_and_boundary_checks():
    crop_rules_dir = ROOT / "memory" / "crop_rules"
    required_rule_files = {
        "_shared.json", "apple.json", "pear.json",
        "lettuce.json", "potato.json", "cucumber.json",
    }
    missing_rule_files = required_rule_files - {path.name for path in crop_rules_dir.glob("*.json")}
    assert not missing_rule_files, f"Missing crop rule files: {sorted(missing_rule_files)}"

    apple_json_path = crop_rules_dir / "apple.json"
    pear_json_path = crop_rules_dir / "pear.json"
    assert apple_json_path.exists() and pear_json_path.exists(), "memory/crop_rules/{apple,pear}.json missing"

    # 6. Assert apple/pear crop files have "note" key mentioning "확인 필요"
    for crop_json_path in (apple_json_path, pear_json_path):
        crop_entry = json.loads(crop_json_path.read_text(encoding="utf-8"))
        assert "note" in crop_entry, f"{crop_json_path.name} missing 'note'"
        assert "확인 필요" in crop_entry["note"], f"{crop_json_path.name} note missing '확인 필요': {crop_entry['note']}"
        guide = crop_entry["temperature_guides"]
        assert len(guide) == 1 and guide[0]["months"] == [4, 5, 6, 7, 8, 9, 10]
        assert "농업·농촌 기후정보시스템" in guide[0]["source"]

    # 7. Boundary check for forbidden accuracy/causal/yield prediction claims in scoped files per CLAUDE.md §9
    import re
    experiment_py_path = SCRIPTS_ML / "crop_literature_anchor_experiment.py"
    crop_rules_files = sorted(crop_rules_dir.glob("*.json"))
    for target_path in (*crop_rules_files, experiment_py_path):
        content = target_path.read_text(encoding="utf-8")
        # No measured accuracy percentage claims (e.g. '정확도 90%', '90% 정확도')
        acc_claims = re.findall(r"정확도\s*[:=]?\s*\d+%", content) + re.findall(r"\d+%\s*정확도", content)
        assert not acc_claims, f"Forbidden measured accuracy claim found in {target_path.name}: {acc_claims}"

        # No yield prediction claims ('수량 예측', '수량예측')
        yield_claims = re.findall(r"수량\s*예측", content)
        assert not yield_claims, f"Forbidden yield prediction claim found in {target_path.name}: {yield_claims}"

        # No affirmative causality claims ('인과' without disclaimer words)
        causal_claims = [
            line.strip()
            for line in content.splitlines()
            if "인과" in line and not any(w in line for w in ("없음", "아님", "금지"))
        ]
        assert not causal_claims, f"Forbidden causality claim found in {target_path.name}: {causal_claims}"



def test_band_score_curve():
    """채점 곡선 계약(scripts/ml/scoring.py). 백엔드 룰 엔진의 _indicator_score와 같아야 한다."""
    from scoring import band_score

    rule = {"optimal_min": 20, "optimal_max": 22, "allowed_min": 15, "allowed_max": 30}
    assert band_score(21, rule) == 100.0, "최적구간은 만점"
    # 최적 이탈 순간 95에서 시작한다 — 100에서 이어지지 않는다.
    assert round(band_score(22.001, rule), 1) == 95.0, "최적 이탈 시작점이 95가 아님"
    # 허용경계는 정확히 60(B등급 하한), 상·하한 양쪽 동일.
    assert round(band_score(30, rule), 1) == 60.0 and round(band_score(15, rule), 1) == 60.0
    # 허용구간은 최적 근처가 완만하고 허용경계 근처가 가파르다.
    assert 95.0 - band_score(24, rule) < band_score(28, rule) - 60.0, "허용구간 곡률 방향 반대"
    # 위험구간은 절벽이 아니라 단조 감소하고, 최적경계에서 완충폭 2배 밖이면 0.
    risk = [band_score(v, rule) for v in (31, 33, 35, 37)]
    assert all(0 < s < 60 for s in risk), risk
    assert all(a > b for a, b in zip(risk, risk[1:])), risk
    assert band_score(38, rule) == 0.0 and band_score(10, rule) == 0.0
    # 완충폭이 없으면 척도를 정할 수 없어 종전대로 즉시 0.
    assert band_score(8, {"optimal_min": 6, "optimal_max": 7}) == 0.0

    # risk_width(전국 실측 산포도)가 있으면 감쇠 거리가 완충폭 대신 그 값이 된다.
    # 백엔드 _risk_score와 같은 계약이다(2026-07-29 개정).
    narrow = {"optimal_min": 6.5, "optimal_max": 7.0, "allowed_min": 6.25, "allowed_max": 7.25}
    wide = {**narrow, "risk_width": 0.4641}
    assert band_score(5.91, narrow) == 0.0, "종전 완충폭(0.25)이면 0점이어야 한다"
    assert 0 < band_score(5.91, wide) < 60, "감쇠폭을 넓혔는데 점수가 안 매겨졌다"
    assert band_score(5.5, wide) == 0.0, "감쇠폭 밖은 여전히 0점(절벽 제거가 0점 제거는 아님)"
    for v in (6.2, 6.1, 6.0, 5.95):
        assert band_score(v, wide) >= band_score(v, narrow), f"넓은 감쇠폭이 더 박하다: {v}"
    assert pd.isna(band_score(None, rule)), "결측은 NaN 유지(강제 대체 금지)"


def test_output_csv_integrity():
    # 8. Output CSV integrity checks
    # 데이터는 레포 루트 /data에 있다(outcomes/data는 이관되지 않음) — 산출 스크립트와 동일 경로.
    experiment_csv = ROOT.parent / "data" / "ml" / "crop_literature_anchor_experiment.csv"
    answer_data_csv = ROOT / "AnswerData.csv"
    regional_score_csv = ROOT / "RegionalScore.csv"

    if experiment_csv.exists():
        df_exp = pd.read_csv(experiment_csv, dtype={"region_code": str})
        assert len(df_exp) == 150, f"experiment.csv row count mismatch: {len(df_exp)}"
        assert df_exp["region_code"].is_unique, "experiment.csv region_code duplicate"
        # 3 existing crops have non-all-NaN temp scores
        for c in ("07001", "03001", "04009"):
            col = f"score_{c}_temp"
            assert col in df_exp.columns, f"Column {col} missing from experiment.csv"
            assert df_exp[col].notna().any(), f"Column {col} is unexpectedly all NaN"
        assert df_exp["score_09001_temp"].notna().any(), "apple temperature score missing"
        assert df_exp["score_09011_temp"].notna().any(), "pear user-specified temperature score missing"

    if answer_data_csv.exists():
        df_ans = pd.read_csv(answer_data_csv)
        assert df_ans["variable"].is_unique, "AnswerData.csv variable column not unique"
        assert not df_ans.empty, "AnswerData.csv is empty"

    if regional_score_csv.exists():
        df_reg = pd.read_csv(regional_score_csv, dtype={"region_code": str})
        assert len(df_reg) == 150, f"RegionalScore.csv row count mismatch: {len(df_reg)}"
        assert df_reg["region_code"].is_unique, "RegionalScore.csv region_code not unique"
        # Existing 3-crop total score columns valid
        for crop_id, name in [("07001", "상추"), ("03001", "감자"), ("04009", "오이")]:
            tot_col = f"total_score_{crop_id}_{name}"
            assert tot_col in df_reg.columns, f"Column {tot_col} missing in RegionalScore.csv"
            assert df_reg[tot_col].between(0, 100).all(), f"Column {tot_col} out of 0-100 bounds"
            assert df_reg[tot_col].gt(0).any(), f"Column {tot_col} has no positive scores"
            assert df_reg[tot_col].nunique() > 1, f"Column {tot_col} has no regional variation"


def main():
    test_crop_anchors_new_entries()
    test_approved_rules_json_and_boundary_checks()
    test_band_score_curve()
    test_output_csv_integrity()
    print("ALL REGRESSION TESTS PASSED.")


if __name__ == "__main__":
    main()
