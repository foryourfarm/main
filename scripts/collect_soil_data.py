"""흙토람 오픈API(SoilExam, SoilExamStat) 전국 벌크 수집 -> data/soil/*.csv (ML용).

법정동코드(STDG_CD) 목록 파일을 순회하며:
  - SoilExam/V2/getSoilExamList  : 동/리 단위 토양검정 화학성 상세정보(페이징)
  - SoilExamStat/V2/getFarmExam*Info (7종) : 시군구/읍면동 단위 농경지화학성 통계(면적)

SoilCharacSctnn(토양특성 단면정보)은 여기 포함하지 않음 — PNU(개별 지번) 단건 조회만
가능해서 전국 벌크 수집 자체가 이 API로는 안 됨(별도 지번 목록 필요, 별도 과제).

법정동코드 파일 형식은 가정하지 않는다(행안부 배포본마다 인코딩/컬럼이 달라짐) — 파일 안에서
10자리 숫자 토큰을 전부 뽑아 중복 제거해서 쓴다.

사용법:
    python scripts/collect_soil_data.py <법정동코드_파일>

출력: data/soil/soil_exam.csv, data/soil/soil_farm_stat.csv
재실행 시 이미 처리된 STDG_CD는 건너뛴다(중간에 죽어도 이어서 가능).
"""

import csv
import re
import sys
import time
from pathlib import Path
from xml.etree import ElementTree

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "soil"
ENV_PATH = ROOT / ".env"

EXAM_BASE = "https://apis.data.go.kr/1390802/SoilEnviron/SoilExam/V2"
STAT_BASE = "https://apis.data.go.kr/1390802/SoilEnviron/SoilExamStat/V2"

# CLAUDE.md §12: rate limit 준수 — 명세서의 초당 최대 트랜잭션 그대로 사용
EXAM_TPS = 30
STAT_TPS = 10
PAGE_SIZE = 100
MAX_RETRIES = 3

STAT_OPERATIONS = [
    "getFarmExamPhInfo",
    "getFarmExamOmInfo",
    "getFarmExamApInfo",
    "getFarmExamKalInfo",
    "getFarmExamCalInfo",
    "getFarmExamMgInfo",
    "getFarmExamSaInfo",
]


def load_service_key() -> str:
    """루트 .env에서 인증키를 읽는다(세 API 모두 같은 발급 키를 씀)."""
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("chemistry_API"):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"{ENV_PATH}에서 chemistry_API 키를 찾지 못함")


def load_stdg_codes(path: Path) -> list[str]:
    """행안부 법정동코드 파일에서 10자리 숫자 토큰만 뽑아 중복 제거(순서 유지)."""
    for enc in ("utf-8", "cp949"):
        try:
            text = path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise RuntimeError(f"{path} 인코딩을 확인할 수 없음(utf-8/cp949 둘 다 실패)")

    seen: dict[str, None] = {}
    for token in re.findall(r"\b\d{10}\b", text):
        seen[token] = None
    return list(seen.keys())


class QuotaExceeded(Exception):
    """429가 반복 재시도로도 안 풀림 — 서비스키 일일/분당 한도 초과로 간주하고 전체 중단."""


# 연속 429 실패가 이 횟수를 넘으면 재시도로 풀릴 일시적 문제가 아니라고 보고 즉시 중단(CLAUDE.md §12:
# 무분별 재호출 금지 — 한도 초과 상태에서 계속 두드리는 건 그 자체가 무분별 호출임).
MAX_CONSECUTIVE_429 = 5
_consecutive_429 = 0


def call(url: str, params: dict) -> tuple[str, str, ElementTree.Element | None]:
    """공통 호출. (result_code, result_msg, body_element) 반환.

    429(요청 한도 초과)는 몇 초 기다린다고 풀리는 경우가 거의 없어서 재시도하지 않고
    바로 "429"로 반환한다 — 호출부가 이 코드를 "실패"로 취급해서 완료 기록을 안 남기게(재실행 시 재조회).
    """
    global _consecutive_429
    for attempt in range(MAX_RETRIES):
        try:
            resp = httpx.get(url, params=params, timeout=10.0)
            if resp.status_code == 429:
                _consecutive_429 += 1
                if _consecutive_429 > MAX_CONSECUTIVE_429:
                    raise QuotaExceeded(
                        f"429가 {_consecutive_429}회 연속 발생(서비스키 요청 한도 초과로 보고 중단합니다). "
                        "잠시 후(또는 다음날 한도 리셋 후) 같은 명령으로 재실행하면 실패한 코드부터 이어서 받습니다."
                    )
                return "429", "Too Many Requests", None
            _consecutive_429 = 0
            resp.raise_for_status()
            root = ElementTree.fromstring(resp.text)
            header = root.find(".//header")
            # 이 API 계열은 오퍼레이션마다 Result_Code/result_Code로 대소문자가 다름(실측 확인됨)
            code = None
            msg = None
            for child in (header if header is not None else []):
                if child.tag.lower() == "result_code":
                    code = child.text
                elif child.tag.lower() == "result_msg":
                    msg = child.text
            return code or "", msg or "", root.find(".//body")
        except (httpx.HTTPError, ElementTree.ParseError) as e:
            if attempt == MAX_RETRIES - 1:
                return "ERROR", str(e), None
            time.sleep(2**attempt)
    return "ERROR", "unreachable", None


def existing_codes(csv_path: Path, key_col: str) -> set[str]:
    if not csv_path.exists():
        return set()
    with csv_path.open(encoding="utf-8", newline="") as f:
        return {row[key_col] for row in csv.DictReader(f) if row.get(key_col)}


def write_rows(csv_path: Path, rows: list[dict], append: bool) -> None:
    if not rows:
        return
    fieldnames = sorted({k for r in rows for k in r})
    # 대표 컬럼은 앞으로
    for pinned in ("stdg_cd", "bjd_nm"):
        if pinned in fieldnames:
            fieldnames.remove(pinned)
            fieldnames.insert(0, pinned)
    mode = "a" if append and csv_path.exists() else "w"
    write_header = mode == "w"
    with csv_path.open(mode, encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def collect_farm_stat(service_key: str, stdg_codes: list[str]) -> None:
    """SoilExamStat 7개 오퍼레이션 -> STDG_CD 단위로 한 행에 합쳐서 저장."""
    out_path = OUT_DIR / "soil_farm_stat.csv"
    done = existing_codes(out_path, "stdg_cd")
    todo = [c for c in stdg_codes if c not in done]
    print(f"[farm_stat] 대상 {len(stdg_codes)}개 중 {len(todo)}개 진행 (기완료 {len(done)}개 스킵)")

    interval = 1.0 / STAT_TPS
    for i, code in enumerate(todo, 1):
        merged: dict[str, str] = {"stdg_cd": code}
        failed = False
        for op in STAT_OPERATIONS:
            try:
                result_code, result_msg, body = call(
                    f"{STAT_BASE}/{op}", {"serviceKey": service_key, "STDG_CD": code}
                )
            except QuotaExceeded as e:
                print(f"  {e}")
                return
            time.sleep(interval)
            if result_code not in ("200", "301"):
                # ERROR/429 등 진짜 실패 — 이 코드는 완료 기록을 남기지 않고 다음 실행 때 재시도
                print(f"  [{op}] {code}: {result_code} {result_msg}")
                failed = True
                continue
            if result_code == "301":
                continue
            item = body.find(".//item") if body is not None else None
            if item is None:
                continue
            for child in item:
                merged[child.tag.lower()] = child.text

        if failed:
            continue  # 기록 안 함 -> 다음 실행 때 이 코드부터 다시 시도
        if len(merged) > 1:  # stdg_cd 말고 실제 값이 하나라도 들어왔으면
            write_rows(out_path, [merged], append=True)
        else:
            write_rows(out_path, [{"stdg_cd": code}], append=True)  # 진짜 데이터 없음(301) 확인됨
        if i % 20 == 0 or i == len(todo):
            print(f"  진행 {i}/{len(todo)}")


def collect_soil_exam(service_key: str, stdg_codes: list[str]) -> None:
    """SoilExam getSoilExamList -> STDG_CD 단위 페이징 수집."""
    out_path = OUT_DIR / "soil_exam.csv"
    done = existing_codes(out_path, "stdg_cd")
    todo = [c for c in stdg_codes if c not in done]
    print(f"[soil_exam] 대상 {len(stdg_codes)}개 중 {len(todo)}개 진행 (기완료 {len(done)}개 스킵)")

    interval = 1.0 / EXAM_TPS
    for i, code in enumerate(todo, 1):
        page_no = 1
        total_count = None
        rows: list[dict] = []
        failed = False
        while total_count is None or len(rows) < total_count:
            try:
                result_code, result_msg, body = call(
                    f"{EXAM_BASE}/getSoilExamList",
                    {
                        "serviceKey": service_key,
                        "Page_Size": PAGE_SIZE,
                        "Page_No": page_no,
                        "STDG_CD": code,
                    },
                )
            except QuotaExceeded as e:
                print(f"  {e}")
                return
            time.sleep(interval)
            if result_code == "301":
                break  # 진짜 데이터 없음 — 확정
            if result_code != "200":
                # ERROR/429 등 진짜 실패 — 완료 기록 안 남기고 다음 실행 때 재시도
                print(f"  [getSoilExamList] {code} p{page_no}: {result_code} {result_msg}")
                failed = True
                break
            total_count = int(body.findtext("Total_Count") or "0")
            items = body.findall(".//item")
            if not items:
                break
            for item in items:
                row = {"stdg_cd": code}
                for child in item:
                    if child.tag != "No":
                        row[child.tag.lower()] = child.text
                rows.append(row)
            page_no += 1

        if failed:
            continue  # 기록 안 함 -> 다음 실행 때 이 코드부터 다시 시도
        write_rows(out_path, rows or [{"stdg_cd": code}], append=True)
        if i % 20 == 0 or i == len(todo):
            print(f"  진행 {i}/{len(todo)} (누적 레코드: 최근 코드 {len(rows)}건)")


def main() -> None:
    if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != "--exam-only"):
        print(f"사용법: python {Path(__file__).name} <법정동코드_파일> [--exam-only]")
        print("  --exam-only: getSoilExamList만 돌림(동/리 단위 코드로 재수집할 때 farm_stat 중복 호출 방지)")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    service_key = load_service_key()
    stdg_codes = load_stdg_codes(Path(sys.argv[1]))
    print(f"법정동코드 {len(stdg_codes)}개 로드")

    if len(sys.argv) == 2:
        collect_farm_stat(service_key, stdg_codes)
    collect_soil_exam(service_key, stdg_codes)


if __name__ == "__main__":
    main()
