"""HWP -> txt 일괄 변환. data/<crop>/*.hwp 를 찾아 같은 이름 .txt로 같은 폴더에 저장한다.

사용법:
    python scripts/hwp_to_txt.py

받은 HWP 파일을 data/<작물>/ 에 그대로 넣고 이 스크립트만 돌리면 된다.
예: data/pear/재배환경.hwp -> data/pear/재배환경.txt (원본 .hwp는 그대로 둠, 이미 변환된 건 건너뜀)

필요 패키지: pip install pyhwp
"""

import shutil
import subprocess
import sys
from pathlib import Path

HWP5TXT = shutil.which("hwp5txt")  # PATH에 있으면 그걸 사용
if HWP5TXT is None:
    # PATH에 없으면 pip install 시 흔히 떨어지는 위치를 직접 지정(환경별로 다르면 여기만 고치면 됨)
    fallback = Path.home() / "AppData/Roaming/Python/Python314/Scripts/hwp5txt.exe"
    HWP5TXT = str(fallback) if fallback.exists() else "hwp5txt"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def convert_one(hwp_path: Path, out_path: Path) -> bool:
    result = subprocess.run(
        [HWP5TXT, str(hwp_path), "--output", str(out_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  실패: {hwp_path.name} -> {result.stderr.strip()[:200]}")
        return False
    return True


def main() -> None:
    if not DATA_DIR.exists():
        print(f"data 폴더가 없습니다: {DATA_DIR}")
        sys.exit(1)

    converted = failed = skipped = 0
    for crop_dir in sorted(DATA_DIR.iterdir()):
        if not crop_dir.is_dir():
            continue
        hwp_files = sorted(crop_dir.glob("*.hwp"))
        if not hwp_files:
            continue
        print(f"[{crop_dir.name}] {len(hwp_files)}개 HWP 발견")
        for hwp_path in hwp_files:
            out_path = crop_dir / f"{hwp_path.stem}.txt"
            if out_path.exists():
                skipped += 1
                continue
            if convert_one(hwp_path, out_path):
                print(f"  완료: {hwp_path.name} -> {out_path.relative_to(DATA_DIR)}")
                converted += 1
            else:
                failed += 1

    print(f"\n총 {converted}개 변환 완료, {skipped}개 이미 있어 건너뜀, {failed}개 실패")


if __name__ == "__main__":
    main()
