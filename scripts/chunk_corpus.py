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

HEADER_RE = re.compile(
    r"^(===.*===|[가-힣]\.\s+\S|\(\d+\)\s|\d+\)\s|\d+\.\s+\S)"
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


def chunk_file(path: Path, crop: str) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    doc_title = path.stem
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
                "source_ref": f"{doc_title} (농촌진흥청 농사로, https://nongsaro.go.kr, 공공누리 제2유형)",
            }
        )
    return records


def main() -> None:
    targets = sys.argv[1:] or [d.name for d in sorted(DATA_DIR.iterdir()) if d.is_dir()]

    for crop in targets:
        crop_dir = DATA_DIR / crop
        if not crop_dir.is_dir():
            print(f"건너뜀 (폴더 없음): {crop}")
            continue
        txt_files = sorted(crop_dir.glob("*.txt"))
        txt_files = [p for p in txt_files if not p.name.startswith("_")]

        all_chunks: list[dict] = []
        for path in txt_files:
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
