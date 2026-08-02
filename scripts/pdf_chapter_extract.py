"""농촌진흥청 농업기술길잡이 PDF → data/<crop>/<챕터>.txt (RAG 코퍼스 원자재).

**왜 필요한가**: 챗봇이 시비 질문에 근거 없는 수치를 지어냈다(실측: "1헥타르당 석회량은
대략 200~50…"). 원인은 코퍼스 빈약함 — 배·감자·오이는 재배관리 정보가 아예 없고
역사·통계뿐이다(`nexttodo.md` "RAG 코퍼스 보강" 참고). 이 스크립트가 그 공백의 실제
출처인 PDF 교본에서 지정한 챕터만 뽑아 기존 `chunk_corpus.py` 파이프라인이 먹는
형식(`data/<crop>/*.txt`)으로 만든다.

**라이선스**: 대상 PDF는 전부 공공누리 제3유형(출처표시+변경금지)이다. 표를 자연어
문장으로 재구성하는 것은 "새로운 창작적 표현"이 아니라 원문 수치를 그대로 다른 형식으로
옮기는 것으로 판단해 진행한다(2026-08-02 팀 결정, `nexttodo.md`에 근거 기록). 상업용금지가
추가로 걸린 문서(사과 6권 신판, 제4유형)는 대상에서 제외 — 같은 내용을 담은 구판(제3유형)을
대신 쓴다.

**표 처리**: PyMuPDF `find_tables()`로 행·열 구조를 복원한다(플레인 텍스트 추출은 표를
"2.5 0.7 1.7" 같은 숫자 수프로 만들어 못 쓴다 — 실측 확인됨). 캡션은 표 bbox 바로 위
텍스트 블록에서 가져온다. 렌더링은 컬럼마다 "라벨: 값"을 나열하는 균일한 방식이다 — 어느
컬럼이 "맥락"이고 어느 게 "측정값"인지는 표마다 달라 자동판별이 불안정하다. 다소 기계적인
문장이 되지만(임베딩 대상이라 사람이 직접 읽는 문장체보다 정확성이 우선) 76~133개 표에
일관되게 적용 가능하다.

**챕터 경계**: "제N장"(아라비아) 또는 "제Ⅰ장"(로마) 헤더가 각 페이지에 러닝헤더로 반복
출현하는 것을 이용해, 그 챕터 번호가 처음 등장하는 페이지 ~ 다음 챕터 시작 전 페이지로
범위를 잡는다. 목차 페이지의 언급은 건너뛴다(SKIP_PAGES).

사용법:
    backend/.venv/Scripts/python.exe scripts/pdf_chapter_extract.py
(PDF_JOBS 상수에 대상을 하드코딩 — 1회성 ETL이라 CLI 인자로 일반화하지 않는다, YAGNI)
"""

import re
import sys
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PDF_DIR = Path.home() / "Downloads"  # 원본 위치. 원본 자체는 리포에 커밋하지 않는다.

ROMAN = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ"
ROMAN_VALUE = {c: i + 1 for i, c in enumerate(ROMAN)}
CHAPTER_RE = re.compile(rf"^제\s?([0-9]+|[{ROMAN}]+)\s?장")
SKIP_PAGES = 10  # 목차·집필진 페이지는 여기까지로 보고 챕터 탐지에서 제외한다.

# 표가 아닌 순수 숫자/기호 줄(페이지 번호 등).
NUMERIC_LINE_RE = re.compile(r"^[\d,.\-~%()\s]+$")

# 러닝헤더/푸터 판정: 챕터 페이지의 이 비율 이상에 나타나는 짧은 줄. 0.5가 아니라 0.4인
# 이유는 "제Ⅴ장 토양 및 비배관리" 같은 헤더가 홀/짝 한쪽 면에만 찍혀 딱 절반 근처가 되기
# 때문이다. 챕터가 짧으면(<MIN_PAGES) 본문이 우연히 반복될 여지가 커서 아예 끄고 간다.
RUNNING_LINE_RATIO = 0.4
RUNNING_LINE_MIN_PAGES = 5
RUNNING_LINE_MAX_CHARS = 40

# (PDF 파일명, 표지에 적힌 정식 제목, 작물 디렉터리, [(챕터번호, 출력 파일명)]).
# 제목은 페이지0에서 자동 추출하지 않고 직접 적는다 — 표지 첫 줄이 대개 홍보 문구라
# ("사과는 영년생 작물로 한번 재식하면…") 자동 추출이 틀린 제목을 출처에 박는다.
# 사과는 상업용금지가 걸린 신판(제4유형) 대신 구판(제3유형)을 쓴다 — nexttodo.md 참고.
PDF_JOBS: list[tuple[str, str, str, list[tuple[int, str]]]] = [
    (
        "24 배_저화질_단면.pdf", "013 배(개정8판, 2020)", "pear",
        # 수확과 저장은 제Ⅷ장이 아니라 **제Ⅶ장**이다. 8로 적혀 있어서 제Ⅷ장 «배 경영»
        # (생산액·경영분석 통계)이 "수확과 저장"이라는 제목을 달고 55청크 들어갔고, 정작
        # 배의 수확·저장 정보는 코퍼스에 하나도 없었다 — 챗봇이 "배 수확 적기"를 물으면
        # 경영 통계를 근거로 받는 상태였다. 경영 챕터는 재배 상담 스코프(§13) 밖이라 뺀다.
        [(5, "과원 관리 기술"), (6, "생리장해와 병해충 방제"), (7, "수확과 저장")],
    ),
    (
        "33 감자_저화질_단면.pdf", "031 감자(개정8판, 2020)", "potato",
        [
            (7, "가꿈꼴(작형)별 재배기술"), (8, "씨감자 생산재배"),
            (9, "수확 후 관리"), (10, "감자 병해충과 방제"),
        ],
    ),
    (
        "농업기술길잡이5_사과재배.PDF", "5 사과재배(개정7판, 2018)", "apple",
        [(4, "정지·전정"), (5, "토양 및 비배관리"), (9, "수확, 선과 및 저장")],
    ),
    (
        # 상추는 처음엔 "이미 재배관리 보유라 스킵"했는데(nexttodo.md), 그 근거였던
        # 농사로 낱개 .txt("재배 환경.txt" 등)는 몇 문단짜리 요약이었다 — 이 책의 제4~7장은
        # 그보다 훨씬 두꺼운 전문(재배 작형별 방법·생리장해 개별 증상·병해충 방제·수확후관리)
        # 이라 겹치지 않는다. 제1~3장(일반현황·생리생태·품종)은 기존 커버리지와 겹쳐서 뺀다.
        "23 상추_저화질_단면.pdf", "160 상추(개정5판, 2020)", "lettuce",
        [(4, "재배"), (5, "생리 장해"), (6, "병해충 생태 및 방제"), (7, "수확 후 관리")],
    ),
]

SOURCE_LINE = (
    "출처: 농촌진흥청 농업기술길잡이 «{title}» "
    "(공공누리 제3유형: 출처표시+변경금지, http://lib.rda.go.kr)"
)


def _chapter_num(line: str) -> int | None:
    m = CHAPTER_RE.match(line)
    if not m:
        return None
    token = m.group(1)
    return int(token) if token.isdigit() else ROMAN_VALUE.get(token)


def find_chapter_ranges(doc: fitz.Document) -> dict[int, tuple[int, int]]:
    """챕터번호 -> (시작 페이지, 끝 페이지), 0-indexed 양끝 포함.

    각 챕터 페이지마다 "제N장 <제목>"이 러닝헤더로 반복되므로, 그 번호가 처음 나온
    페이지를 시작으로 본다. 목차 페이지(SKIP_PAGES 이전)의 언급은 챕터 시작이 아니므로
    건너뛴다 — 안 그러면 모든 챕터가 목차 페이지에서 "시작"한 것으로 잘못 잡힌다.
    """
    first_seen: dict[int, int] = {}
    for p in range(SKIP_PAGES, len(doc)):
        for line in doc[p].get_text().splitlines():
            num = _chapter_num(line.strip())
            if num is not None and num not in first_seen:
                first_seen[num] = p
    ordered = sorted(first_seen.items())
    ranges: dict[int, tuple[int, int]] = {}
    for i, (num, start) in enumerate(ordered):
        end = ordered[i + 1][1] - 1 if i + 1 < len(ordered) else len(doc) - 1
        ranges[num] = (start, _trim_trailing_pages(doc, num, start, end))
    return ranges


# 러닝헤더가 없는 후행 페이지를 몇 장부터 "챕터 밖"으로 볼지. 1장은 자르지 않는다 —
# 챕터 사이 간지·여백 페이지라 어차피 내용이 없고, 전 챕터에서 0~1장으로 일정하다.
TRAILING_TRIM_MIN = 2


def _trim_trailing_pages(doc: fitz.Document, num: int, start: int, end: int) -> int:
    """챕터 러닝헤더가 사라진 뒤로 이어지는 후행 페이지를 범위에서 뺀다.

    마지막 챕터는 `end`가 문서 끝이라 뒤에 붙은 **특집·부록을 통째로 삼킨다** — 실측:
    배 제8장(수확과 저장)이 p379~387의 "특집 농작업 안전관리"를 흡수해, 배와 무관한
    안전 점검표가 배 코퍼스에 5청크 들어갔다(감자 제11장도 6페이지 동일). 챕터 본문
    페이지에는 "제N장"이 러닝헤더로 반복되므로, 그게 끊긴 뒤 구간을 잘라낸다.
    """
    last_with_header = start
    for p in range(start, end + 1):
        if any(_chapter_num(line.strip()) == num for line in doc[p].get_text().splitlines()):
            last_with_header = p
    return end if end - last_with_header < TRAILING_TRIM_MIN else last_with_header


def find_running_lines(doc: fitz.Document, start: int, end: int) -> set[str]:
    """챕터 페이지 다수에 반복 출현하는 짧은 줄 = 러닝헤더/푸터.

    종전에는 블랙리스트 5개("농업기술길잡이"·작물명)로 걸렀는데, 실제로는 문서마다
    다른 장식 줄이 본문에 섞여 들어왔다(실측: "사과재배", "A p p l e c u l t i v a t i o n",
    "제Ⅴ장 토양 및 비배관리", "농. 업. 기. 술. 길. 잡. 이"). 마지막 것은 `chunk_corpus`의
    헤더 정규식("가. ")에까지 걸려 **섹션 제목 자리를 차지했다.** 문서별로 블랙리스트를
    늘리는 대신 "여러 페이지에 똑같이 나오는 짧은 줄"이라는 러닝헤더의 정의 자체로 잡는다.
    """
    n_pages = end - start + 1
    if n_pages < RUNNING_LINE_MIN_PAGES:
        return set()
    counter: Counter[str] = Counter()
    for p in range(start, end + 1):
        counter.update(
            {
                s
                for line in doc[p].get_text().splitlines()
                if 0 < len(s := line.strip()) <= RUNNING_LINE_MAX_CHARS
            }
        )
    return {line for line, c in counter.items() if c >= n_pages * RUNNING_LINE_RATIO}


def _fill_header_row(row: list[str | None]) -> list[str | None]:
    """병합된 헤더 셀(None)을 왼쪽 값으로 채운다 — colspan 헤더 복원."""
    filled: list[str | None] = []
    last: str | None = None
    for cell in row:
        if cell is not None:
            last = cell.replace("\n", " ").strip()
        filled.append(last)
    return filled


def _is_header_row(row: list[str | None]) -> bool:
    """행의 값 있는 셀이 전부 순수 숫자가 아니면 헤더 행으로 본다.

    데이터 행은 최소 하나(수량·성분량 등)는 순수 숫자다. "1년차"처럼 라벨에 숫자가
    섞인 셀은 전체가 숫자 패턴이 아니므로 헤더로 오판하지 않는다.

    **셀 안에 개행으로 여러 값이 압축된 경우**(가로 구분선 없는 표, `_split_compressed_rows`
    참고)는 셀 전체가 아니라 줄 단위로 쪼개서 검사한다 — 안 그러면 "8.82\\n2.94\\n5.88"
    같은 압축 데이터 셀이 (개행 때문에) 순수 숫자 패턴에 안 걸려 헤더로 오판되고, 그
    표의 데이터 행 전체가 사라진다(실측: 이 버그로 표 하나가 통째로 날아갔었다).

    한계: 3행 이상 헤더는 지원하지 않는다(관찰된 최대가 2행이라 여기서 멈춘다 —
    더 필요해지면 반복 횟수를 늘리면 된다).
    """
    pieces = [p.strip() for c in row if c for p in c.split("\n") if p.strip()]
    if not pieces:
        return False
    return not any(re.fullmatch(r"[\d,.\-~%]+", p) for p in pieces)


def _merge_continuation_rows(rows: list[list[str | None]]) -> list[list[str | None]]:
    """첫 컬럼만 있고 나머지가 전부 빈 행을 앞 행의 라벨에 이어 붙인다.

    실측(사과구판 표 5-25 «사과원 토양 화학성 변화»)의 원본 추출:

        ["1987", "6.4\\n6.2\\n6.6", "10.4\\n18.0\\n21.9", ...]
        ["1992", None, None, ...]
        ["2002", None, None, ...]

    연도 라벨은 세 물리행에 걸쳐 있는데 값은 첫 행 셀에 개행으로 압축돼 있다. 그대로 두면
    `_split_compressed_rows`가 첫 컬럼 줄 수(1)만 보고 안 쪼개서 "1987년 pH 6.4 6.2 6.6"이
    되고, 라벨만 보고 쪼개면 세 행 전부 1987이 된다 — **둘 다 사실과 다른 문장을 만든다**
    (1992·2002 행은 값이 없어 통째로 버려지기까지 했다). 라벨을 먼저 한 셀로 모아두면
    줄 수가 값 컬럼과 맞아 정상적으로 풀린다.
    """
    out: list[list[str | None]] = []
    for row in rows:
        head, rest = (row[0] if row else None), row[1:]
        if out and head and not any(c and c.strip() for c in rest):
            out[-1][0] = f"{out[-1][0]}\n{head}" if out[-1][0] else head
        else:
            out.append(list(row))
    return out


def _split_compressed_rows(row: list[str | None]) -> list[list[str | None]]:
    """가로 구분선이 없는 표에서, 여러 논리행이 한 물리행에 개행으로 압축된 걸 풀어낸다.

    실측(사과구판 표 5-13): PyMuPDF가 5개 연차를 별도 행이 아니라 셀 하나에
    `"1~4\\n5~9\\n10~14\\n15~19\\n20년 이상"`로 뭉쳐 반환했다(같은 표를 신판 PDF에서 뽑았을
    땐 5개 행으로 정상 분리됐다 — 원본 표에 셀 경계선이 있느냐 없느냐 차이로 보인다).

    논리행 수는 **셀들의 최대 줄 수**다. 종전에는 첫 컬럼의 줄 수로 봤는데, 라벨이 한 줄이고
    값 컬럼만 여러 줄인 표(표 5-5·5-25 등 20건 실측)에서 n=1이 되어 안 쪼개졌고, 렌더링이
    개행을 공백으로 눕히면서 "건전(%): 18.9 56.1 81.8"처럼 **어느 값이 어느 조건인지 사라진
    문장**이 됐다. 최대값을 쓰되 **같은 줄 수를 가진 컬럼이 2개 이상일 때만** 쪼갠다 —
    한 컬럼만 여러 줄이면 그건 논리행이 아니라 여러 줄짜리 각주다.

    다른 컬럼은: 줄 수가 같으면 그대로 대응시키고, 1줄이면(표 전체에 걸리는 라벨·비고 등)
    모든 논리행에 반복하며, 그 외(줄 수가 다른데 1도 아님 — 대개 여러 행에 걸친 각주)는
    쪼개지 않고 통째로 모든 논리행에 붙인다(정보를 자르는 것보다 중복이 낫다, §12).
    """
    parts = [c.split("\n") if c else [c] for c in row]
    counts = [len(p) for p in parts if p and p[0] is not None]
    n = max(counts, default=1)
    if n <= 1 or counts.count(n) < 2:
        return [row]
    out: list[list[str | None]] = []
    for i in range(n):
        new_row = []
        for p in parts:
            if len(p) == n:
                new_row.append(p[i])
            elif len(p) == 1:
                new_row.append(p[0])
            else:
                new_row.append(" / ".join(x for x in p if x))
        out.append(new_row)
    return out


# 실행마다 초기화되는 간이 통계 — 표 인식이 얼마나 깨졌는지 눈으로 확인하기 위함이다.
# 정식 테스트가 아니라 1회성 ETL 실행 로그다(리포의 다른 scripts/*.py와 같은 패턴).
STATS = {"tables_seen": 0, "tables_dropped_empty": 0, "rows_dropped_no_value": 0}


def render_table(rows: list[list[str | None]], caption: str | None) -> str | None:
    """표 → 자연어 문장들. 컬럼마다 "라벨: 값"을 나열하는 균일한 방식(모듈 docstring 참고)."""
    STATS["tables_seen"] += 1
    if not rows:
        return None
    header_rows = [rows[0]]
    if len(rows) > 1 and _is_header_row(rows[1]):
        header_rows.append(rows[1])
    data_rows = [
        expanded
        for row in _merge_continuation_rows(rows[len(header_rows) :])
        for expanded in _split_compressed_rows(row)
    ]
    if not data_rows:
        return None

    filled = [_fill_header_row(r) for r in header_rows]
    n_cols = len(rows[0])
    labels = []
    for col in range(n_cols):
        parts = []
        for r in filled:
            if col < len(r) and r[col] and r[col] not in parts:
                parts.append(r[col])
        labels.append(" ".join(parts) if parts else f"열{col+1}")

    sentences = []
    for row in data_rows:
        pairs = []
        for col, cell in enumerate(row):
            if not cell or cell.strip() in ("-", ""):
                continue
            pairs.append(f"{labels[col]}: {cell.replace(chr(10), ' ').strip()}")
        # 라벨 하나뿐이고 나머지 컬럼이 전부 빈 행은 정보가 없다 — "구분: 인(g/kg)"처럼
        # 이름만 있고 값이 없는 조각을 코퍼스에 넣지 않는다. 드물게 원본 표 자체의 셀
        # 정렬이 깨진 경우(가로 구분선 없는 표에서 PyMuPDF가 데이터를 못 붙이는 경우)에
        # 나온다 — 값을 지어낼 순 없으니 조용히 버린다(§12, 없는 값을 만들지 않는다).
        if len(pairs) >= 2:
            # 끝에 마침표를 붙인다 — chunk_corpus.split_long_body의 문장분할 정규식이
            # "다./요./.  " 뒤에서만 자르는데, 표 문장은 숫자로 끝나 안 걸린다. 마침표가
            # 없으면 표 하나가 통째로 안 잘리는 거대 청크가 된다(실측: 4,800자까지 관측).
            sentences.append(", ".join(pairs) + ".")
        else:
            STATS["rows_dropped_no_value"] += 1
    if not sentences:
        STATS["tables_dropped_empty"] += 1
        return None

    prefix = f"[{caption}] " if caption else "[표] "
    return "\n".join(f"{prefix}{s}" for s in sentences)


def _center_inside(block_bbox: tuple[float, float, float, float], table_bbox) -> bool:
    """블록 중심점이 표 bbox 안에 있는지. 변 하나만 보는 부분 비교는 표 옆 블록을
    잘못 표 내부로 오판할 수 있어(예: y만 겹치고 x는 전혀 다른 블록) 중심점으로 판정한다."""
    x0, y0, x1, y1 = block_bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return table_bbox[0] <= cx <= table_bbox[2] and table_bbox[1] <= cy <= table_bbox[3]


def extract_chapter(doc: fitz.Document, start: int, end: int) -> str:
    """페이지 범위를 읽기 순서대로 프로즈+표문장 혼합 텍스트로."""
    running = find_running_lines(doc, start, end)
    out_lines: list[str] = []
    for p in range(start, end + 1):
        page = doc[p]
        tables = page.find_tables()
        table_bboxes = [t.bbox for t in tables.tables]
        blocks = page.get_text("blocks")

        # (y0, kind, text) 리스트를 만들어 읽기 순서(y좌표)로 합친다.
        items: list[tuple[float, str]] = []
        for t in tables.tables:
            # 캡션 후보: 표 바로 위, 다른 표 안에 없는 가장 가까운 블록.
            above = [
                b for b in blocks
                if b[3] <= t.bbox[1]
                and not any(
                    _center_inside((b[0], b[1], b[2], b[3]), bb)
                    for bb in table_bboxes if bb != t.bbox
                )
            ]
            caption = None
            if above:
                above.sort(key=lambda b: -b[3])
                cand = above[0][4].strip().replace("\n", " ")
                if cand and cand not in running and not NUMERIC_LINE_RE.match(cand):
                    caption = cand
            rendered = render_table(t.extract(), caption)
            if rendered:
                items.append((t.bbox[1], rendered))

        for b in blocks:
            x0, y0, x1, y1, text, *_ = b
            # 표 내부 블록은 건너뛴다 — render_table로 이미 반영됨.
            if any(_center_inside((x0, y0, x1, y1), bb) for bb in table_bboxes):
                continue
            # 러닝헤더가 블록의 첫 줄이 아닐 수 있다(예: "제5장┃토양 및 비배관리\n농업
            # 기술길잡이" 2줄짜리 블록) — 줄 단위로 걸러야 살아남는 걸 막는다. 페이지
            # 번호도 줄 단위로 뺀다: 블록 전체를 보면 본문에 섞인 "139" 한 줄이 남는다.
            kept = [
                s
                for ln in text.splitlines()
                if (s := ln.strip()) and s not in running and not NUMERIC_LINE_RE.match(s)
            ]
            stripped = "\n".join(kept).strip()
            if not stripped:
                continue
            items.append((y0, stripped))

        items.sort(key=lambda t: t[0])
        out_lines.extend(text for _, text in items)
    return "\n".join(out_lines)


def main() -> None:
    for pdf_name, title, crop, chapters in PDF_JOBS:
        pdf_path = PDF_DIR / pdf_name
        if not pdf_path.exists():
            print(f"[확인 필요] 파일 없음: {pdf_path}")
            continue
        doc = fitz.open(pdf_path)
        ranges = find_chapter_ranges(doc)

        for num, out_name in chapters:
            if num not in ranges:
                print(f"[확인 필요] {pdf_name}: 제{num}장 못 찾음")
                continue
            start, end = ranges[num]
            body = extract_chapter(doc, start, end)
            out_path = DATA_DIR / crop / f"{out_name}.txt"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            header = f"{out_name}\n{SOURCE_LINE.format(title=title)}\n\n"
            out_path.write_text(header + body, encoding="utf-8")
            print(f"{crop}/{out_name}.txt  (제{num}장, p{start}~{end}, {len(body):,}자)")
        doc.close()

    seen = STATS["tables_seen"] or 1
    print(
        f"\n표 처리 통계: 인식 {STATS['tables_seen']}개 / "
        f"완전히 못 씀 {STATS['tables_dropped_empty']}개 "
        f"({STATS['tables_dropped_empty']/seen*100:.0f}%) / "
        f"값 없어 버린 행 {STATS['rows_dropped_no_value']}개 "
        "— PyMuPDF가 원본 표의 셀 정렬 자체를 못 잡은 경우다(가로 구분선 없는 표에서 "
        "가끔 발생, 실측: 사과구판 표 5-10). 값을 지어내지 않고 버렸으니 안전하지만, "
        "그 표의 정보는 코퍼스에 안 들어간다."
    )


def selfcheck() -> None:
    """표 행 복원 로직 자가검증(PDF 없이 실행 가능): python scripts/pdf_chapter_extract.py --selfcheck"""
    # 사과구판 표 5-25 원본 추출 그대로. 연도 라벨이 3행에 걸쳐 있고 값은 첫 행에 압축.
    rows = [
        ["구분", "pH\n(1:2.5)", "유기물\n(g/kg)"],
        ["1987", "6.4\n6.2\n6.6", "10.4\n18.0\n21.9"],
        ["1992", None, None],
        ["2002", None, None],
    ]
    text = render_table(rows, "표 5-25 사과원 토양 화학성 변화")
    assert text is not None
    lines = text.splitlines()
    assert len(lines) == 3, lines
    assert "구분: 1987, pH (1:2.5): 6.4, 유기물 (g/kg): 10.4." in lines[0], lines[0]
    assert "구분: 2002, pH (1:2.5): 6.6, 유기물 (g/kg): 21.9." in lines[2], lines[2]

    # 사과구판 표 5-5: 라벨은 한 줄인데 값 컬럼만 3줄 — 전 컬럼에 반복돼야 한다.
    text = render_table(
        [["구분", None, "건전(%)"], ["재식 2년 후", "20cm\n45\n75", "18.9\n56.1\n81.8"]], None
    )
    assert text is not None and len(text.splitlines()) == 3, text
    assert "구분: 45, 건전(%): 56.1." in text.splitlines()[1], text

    # 여러 줄 셀이 하나뿐이면 각주다 — 쪼개면 안 된다.
    assert _split_compressed_rows(["질소", "5.8", "주) 수령 2년차\n인산 별도"]) == [
        ["질소", "5.8", "주) 수령 2년차\n인산 별도"]
    ]
    print("selfcheck OK")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        main()
