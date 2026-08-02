"""data/<crop>/*.doc (농사로 웹페이지 저장본) -> data/<crop>/*.txt

**왜 필요한가**: 오이·상추 코퍼스가 각각 17·16청크로 빈약해 nexttodo.md는 "오이는
스캔본 PDF라 OCR 없이 불가"로 적어뒀는데, 그건 `~/Downloads`의 138MB PDF 얘기였다.
정작 `data/cucumber/`·`data/lettuce/`에는 병해충방제·본포관리·생리장해·재배동향·
파종및육묘 등 재배관리 정보가 담긴 `.doc` 파일이 이미 13개 있었다 — 다만
`chunk_corpus.py`가 `*.txt`만 글롭해서 조용히 건너뛰고 있었다(스캔본 문제가 아니라
파일 형식 필터링 문제, 실측: `file` 명령으로 확인).

**형식이 둘 섞여 있다**(`.doc` 확장자를 붙였지만 실제 내용은 다름, `file` 명령으로 실측):
- 12개는 **HTML**(농사로 페이지를 "다른 이름으로 저장"한 것 — `nongsaro.go.kr` CSS 링크로
  확인). UTF-8, 태그 벗기고 개행 정리하면 된다.
- 1개(`오이-오이-병해충방제.doc`)는 진짜 **Word 2007+(docx, zip)**. `word/document.xml`을
  표준 라이브러리 `zipfile`+`xml.etree`로 읽는다 — python-docx는 이 하나 때문에 새
  의존성을 추가할 정도는 아니다(YAGNI).

사용법:
    backend/.venv/Scripts/python.exe scripts/nongsaro_doc_extract.py
(대상은 DOC_DIR 안의 모든 *.doc를 자동 스캔 — PDF와 달리 챕터 지정이 필요 없어 하드코딩 목록이
 없다)
"""

import html
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CROP_DIRS = ("apple", "pear", "cucumber", "potato", "lettuce")

BLOCK_TAG_RE = re.compile(r"<br\s*/?>|</p>|</div>|</td>|</tr>|</li>", re.IGNORECASE)
ANY_TAG_RE = re.compile(r"<[^>]+>")

# "오이-오이-병해충방제" -> "병해충방제" (작물명이 두 번 반복되는 농사로 파일명 규칙).
CROP_PREFIX_RE = re.compile(r"^([가-힣]+)-\1-")

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_html_doc(raw: str) -> str:
    """농사로 페이지 저장본(HTML) -> 평문. 개행 태그만 줄바꿈으로 바꾸고 나머지는 벗긴다.

    원본 HTML 자체가 손편집처럼 텍스트 노드 중간에 개행을 넣어 저장돼 있다(실측:
    `"정지,\\n유인 및 잎의\\n관리"` — <span> 태그 **안에** 리터럴 개행이 있다, 렌더링
    폭에 맞춘 줄바꿈이지 문장 경계가 아니다). 태그만 벗기고 이 개행을 그대로 두면
    "구분: 재식 2년 후" 같은 표 문장이 단어 하나마다 한 줄이 되어 청킹 단계에서 문장
    경계를 못 찾고(§HEADER_RE·split_long_body 둘 다 줄 단위) MAX_CHARS 도달 시점에서
    표 중간을 그냥 잘라버린다 — 실측: 오이 시비량 표가 안 관련 항목(정식기별 수량표)과
    한 청크에 묶여 뒤쪽 절반이 잘려나갔다. 태그를 건드리기 전에 원본의 리터럴 개행부터
    공백으로 접어서 없앤다.
    """
    text = html.unescape(raw)
    text = re.sub(r"[\r\n]+", " ", text)  # 원본 텍스트 노드 안의 줄바꿈은 word-wrap이지 문장 경계가 아니다
    text = BLOCK_TAG_RE.sub("\n", text)
    text = ANY_TAG_RE.sub("", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def extract_docx(path: Path) -> str:
    """진짜 Word(zip) 문서 -> 평문. <w:p>(문단)마다 한 줄, <w:t>(텍스트 런) 이어붙임."""
    with zipfile.ZipFile(path) as z:
        xml_bytes = z.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    lines = []
    for para in root.iter(f"{W_NS}p"):
        text = "".join(t.text or "" for t in para.iter(f"{W_NS}t"))
        if text.strip():
            lines.append(text.strip())
    return "\n".join(lines)


def is_docx(path: Path) -> bool:
    with path.open("rb") as f:
        return f.read(2) == b"PK"  # zip 매직바이트. HTML 저장본은 아니다.


def main() -> None:
    for crop in CROP_DIRS:
        crop_dir = DATA_DIR / crop
        for doc_path in sorted(crop_dir.glob("*.doc")):
            out_name = CROP_PREFIX_RE.sub("", doc_path.stem)
            out_path = crop_dir / f"{out_name}.txt"
            if is_docx(doc_path):
                body = extract_docx(doc_path)
            else:
                body = extract_html_doc(doc_path.read_text(encoding="utf-8"))
            if not body.strip():
                print(f"[건너뜀] 빈 본문: {doc_path.name}")
                continue
            out_path.write_text(body, encoding="utf-8")
            print(f"{crop}/{out_name}.txt  ({doc_path.name}, {len(body):,}자)")


if __name__ == "__main__":
    main()
