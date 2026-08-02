"""data/<crop>/*.txt -> 청킹 -> data/<crop>/_chunks.jsonl

농사로 문서는 "가./나./다.", "(1)/(2)", "1)/2)", "===섹션===" 식 헤더로 구획되어 있어
그 경계를 기준으로 나누고, 너무 작은 섹션은 합치고 너무 큰 섹션은 문장 단위로 다시 쪼갠다.

사용법:
    python scripts/chunk_corpus.py            # data/ 전체
    python scripts/chunk_corpus.py apple       # 특정 작물만

출력: data/<crop>/_chunks.jsonl (한 줄 = 청크 하나, 임베딩 전 중간 산출물)
"""

import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# data/ 아래에는 코퍼스 말고도 원자재 폴더(raw·soil·aws_daily_cache)가 있다. 인자 없이 돌리면
# 그쪽까지 청킹해서 `data/soil/_chunks.jsonl`(법정동 코드 목록 184KB)처럼 쓸모없는 산출물이
# 생겼다 — `embed_corpus.py`가 crop 매핑 없는 폴더를 건너뛰어 DB엔 안 들어갔을 뿐이다.
CROP_DIRS = ("apple", "pear", "cucumber", "potato", "lettuce")

HEADER_RE = re.compile(
    # [가-힣]\)\s — PDF 교본이 쓰는 "가) 질소" 형태. 농사로 원본은 "가."(마침표)를 쓰는데
    # PDF 추출 텍스트는 상당수가 괄호형이라(사과 92건·상추 76건 실측) 이게 없으면 그
    # 섹션들이 헤더 없는 본문으로 뭉개진다.
    r"^(===.*===|[가-힣]\.\s+\S|[가-힣]\)\s+\S|\(\d+\)\s|\d+\)\s|\d+\.\s+\S)"
)

TARGET_CHARS = 700  # 이 정도까지는 섹션을 합쳐서 채운다
MAX_CHARS = 1200  # 이걸 넘으면 문장 단위로 강제 분할
MIN_CHARS = 30  # 이보다 짧은 조각(예: 제목 한 줄)은 TARGET을 넘더라도 무조건 다음과 합친다


def split_into_sections(text: str) -> list[tuple[str | None, str]]:
    """헤더 줄 기준으로 (헤더 또는 None, 본문) 리스트로 나눈다."""
    sections: list[tuple[str | None, list[str]]] = []
    current_header: str | None = None
    current_body: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if HEADER_RE.match(stripped):
            if current_body or current_header:
                sections.append((current_header, current_body))
            current_header = stripped
            current_body = []
        elif stripped:
            current_body.append(stripped)
    if current_body or current_header:
        sections.append((current_header, current_body))

    return [(h, "\n".join(b)) for h, b in sections if "\n".join(b).strip()]


def split_long_body(body: str, max_chars: int) -> list[str]:
    """섹션 하나가 너무 길면 문장(다./함./음./까?/요?) 경계로 다시 쪼갠다."""
    if len(body) <= max_chars:
        return [body]
    sentences = re.split(r"(?<=[.!?다요]\s)", body)
    chunks, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) > max_chars and buf:
            chunks.append(buf.strip())
            buf = s
        else:
            buf += s
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


def merge_and_split(sections: list[tuple[str | None, str]]) -> list[dict]:
    """작은 섹션은 합치고, 큰 섹션은 쪼개서 최종 청크 리스트를 만든다."""
    out = []
    buf_header = None
    buf_body = ""

    def flush():
        nonlocal buf_header, buf_body
        if buf_body.strip():
            for piece in split_long_body(buf_body.strip(), MAX_CHARS):
                out.append({"section": buf_header, "content": piece})
        buf_header, buf_body = None, ""

    for header, body in sections:
        candidate = (buf_body + "\n" + body).strip() if buf_body else body
        if len(candidate) > TARGET_CHARS and len(buf_body) >= MIN_CHARS:
            flush()
            buf_header, buf_body = header, body
        else:
            if buf_header is None:
                buf_header = header
            buf_body = candidate
    flush()
    return out


DEFAULT_SOURCE = "{doc_title} (농촌진흥청 농사로, https://nongsaro.go.kr, 공공누리 제2유형)"


def _source_ref(text: str, doc_title: str) -> str:
    """파일 본문의 "출처: ..." 줄을 우선 쓴다. 없으면 농사로 기본값으로 폴백한다.

    코퍼스에 두 번째 출처(PDF 교본, 공공누리 제3유형)가 섞이면서 필요해졌다 —
    전에는 전부 농사로뿐이라 하드코딩이 맞았지만, 이제 그대로 두면 PDF 유래 조각도
    "농사로"로 잘못 표기된다(§12 출처 기록 정확성 위반).
    """
    first_line = text.splitlines()[0].strip() if text.strip() else ""
    for line in text.splitlines()[:5]:
        if line.strip().startswith("출처:"):
            return line.strip().removeprefix("출처:").strip()
    return DEFAULT_SOURCE.format(doc_title=doc_title)


MOJIBAKE_RATIO = 0.1  # 본문의 이 비율 이상이 '?'면 인코딩이 깨진 파일로 본다.


def is_mojibake(text: str) -> bool:
    """한글이 '?'(0x3F)로 치환돼 내용이 사라진 파일인지.

    실측: `data/lettuce/상추-상추-*.txt` 5개가 한글이 전부 물음표로 바뀐 채 들어와 있었고
    (원본이 .doc인데 잘못된 코드페이지로 변환된 것으로 보인다) 그대로 청킹·임베딩돼
    **챗봇 근거로 실제 검색됐다**(상추 발아온도 질문의 3순위). 정보가 0인데 자리를 차지하니
    없는 것보다 나쁘다 — 파일을 지워도 같은 경로로 다시 들어올 수 있어 여기서 막는다.
    """
    body = text.strip()
    return bool(body) and body.count("?") / len(body) >= MOJIBAKE_RATIO


def chunk_file(path: Path, crop: str) -> list[dict]:
    # utf-8-sig: 농사로에서 받은 txt 일부에 BOM이 있어 첫 청크 앞머리에 U+FEFF가 그대로
    # 실렸다(12건 실측). 임베딩 입력에 들어가는 보이지 않는 잡음이라 진입점에서 없앤다.
    text = path.read_text(encoding="utf-8-sig")
    doc_title = path.stem
    source_ref = _source_ref(text, doc_title)
    sections = split_into_sections(text)
    chunks = merge_and_split(sections)
    records = []
    for i, c in enumerate(chunks):
        records.append(
            {
                "crop": crop,
                "doc_title": doc_title,
                "section": c["section"],
                "chunk_index": i,
                "content": c["content"],
                "char_count": len(c["content"]),
                "source_ref": source_ref,
            }
        )
    return records


def main() -> None:
    targets = sys.argv[1:] or list(CROP_DIRS)

    for crop in targets:
        crop_dir = DATA_DIR / crop
        if not crop_dir.is_dir():
            print(f"건너뜀 (폴더 없음): {crop}")
            continue
        txt_files = sorted(crop_dir.glob("*.txt"))
        txt_files = [p for p in txt_files if not p.name.startswith("_")]

        all_chunks: list[dict] = []
        for path in txt_files:
            if is_mojibake(path.read_text(encoding="utf-8-sig")):
                print(f"  [건너뜀] 인코딩 깨짐(한글이 '?'로 치환됨): {path.name}")
                continue
            all_chunks.extend(chunk_file(path, crop))

        out_path = crop_dir / "_chunks.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for rec in all_chunks:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        sizes = [c["char_count"] for c in all_chunks]
        avg = sum(sizes) / len(sizes) if sizes else 0
        print(
            f"[{crop}] 문서 {len(txt_files)}개 -> 청크 {len(all_chunks)}개 "
            f"(평균 {avg:.0f}자, 최소 {min(sizes) if sizes else 0}자, 최대 {max(sizes) if sizes else 0}자) "
            f"-> {out_path.relative_to(DATA_DIR.parent)}"
        )


if __name__ == "__main__":
    main()
