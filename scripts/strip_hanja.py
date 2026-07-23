"""data/ 안의 파일명·본문에서 한자(CJK 통합 한자)를 전부 제거한다.

한자 섞인 파일명(예: 겹무늬썩음병(輪紋病).txt)이 유니코드 정규화(NFC/NFD) 차이로
글롭/매칭에서 조용히 안 잡히는 문제가 있어, 애초에 한자를 없애 그 문제 자체를 제거한다.

사용법:
    python scripts/strip_hanja.py
"""

import re
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# CJK 통합 한자(기본 영역) + 확장 A. 한글/일본어 가나는 이 범위 밖이라 안 건드림.
HANJA_RE = re.compile(r"[一-鿿㐀-䶿]")


def clean_text(s: str) -> str:
    s = unicodedata.normalize("NFC", s)  # 파일명이 NFD(분해형)로 저장돼 한자 정규식이 안 잡히는 경우 방지
    s = HANJA_RE.sub("", s)
    s = re.sub(r"\(\s*\)", "", s)  # 한자 지우고 남은 빈 괄호 "()"
    s = re.sub(r"[ \t]{2,}", " ", s)  # 중복 공백 정리
    return s


def main() -> None:
    renamed = cleaned_content = 0

    for crop_dir in sorted(DATA_DIR.iterdir()):
        if not crop_dir.is_dir():
            continue
        for path in sorted(crop_dir.glob("*.txt")):
            # 1) 본문 정리
            text = path.read_text(encoding="utf-8")
            new_text = clean_text(text)
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
                cleaned_content += 1

            # 2) 파일명 정리
            new_name = clean_text(path.stem).strip() + path.suffix
            if new_name != path.name:
                new_path = path.with_name(new_name)
                path.rename(new_path)
                print(f"이름변경: {path.name} -> {new_name}")
                renamed += 1

    print(f"\n파일명 변경 {renamed}건, 본문 수정 {cleaned_content}건")


if __name__ == "__main__":
    main()
