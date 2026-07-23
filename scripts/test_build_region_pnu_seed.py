"""build_region_pnu_seed.py의 DBF 파서 self-check. pytest 없이 assert만으로 검증.

사용법: python scripts/test_build_region_pnu_seed.py
"""

import struct
import tempfile
from pathlib import Path

from build_region_pnu_seed import find_dbf, read_first_pnu


def _make_dbf(path: Path, records: list[tuple[bool, str]]) -> None:
    """records: [(is_deleted, pnu_value), ...]. 필드는 PNU(C, 19) 하나뿐인 최소 DBF."""
    field_name = b"PNU".ljust(11, b"\x00")
    field_desc = field_name + b"C" + b"\x00" * 4 + bytes([19]) + b"\x00" * 15
    header_len = 32 + 32 + 1
    record_len = 1 + 19

    header = bytearray(32)
    header[0] = 0x03
    struct.pack_into("<I", header, 4, len(records))
    struct.pack_into("<H", header, 8, header_len)
    struct.pack_into("<H", header, 10, record_len)

    body = bytearray()
    for is_deleted, pnu in records:
        body += b"*" if is_deleted else b" "
        body += pnu.encode("latin1").ljust(19, b" ")[:19]
    body += b"\x1a"  # EOF marker

    path.write_bytes(bytes(header) + field_desc + b"\r" + bytes(body))


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        dbf_path = tmp_path / "LSMD_CONT_LDREG_11110_202607.dbf"
        _make_dbf(
            dbf_path,
            [(True, "9999999999999999999"), (False, "1111000000100010000")],
        )

        result = read_first_pnu(dbf_path)
        assert result == "1111000000100010000", f"삭제 레코드를 건너뛰고 첫 유효 PNU를 읽어야 함, got={result}"

        found = find_dbf(tmp_path, "11110")
        assert found == dbf_path, f"5자리 시군구 코드로 dbf를 찾아야 함, got={found}"

        assert find_dbf(tmp_path, "99999") is None, "매칭 없는 코드는 None을 반환해야 함"

        empty_dbf = tmp_path / "LSMD_CONT_LDREG_11170_202607.dbf"
        _make_dbf(empty_dbf, [(True, "0000000000000000000")])
        assert read_first_pnu(empty_dbf) is None, "유효 레코드가 없으면 None을 반환해야 함"

        junk_dbf = tmp_path / "LSMD_CONT_LDREG_47850_202607.dbf"
        _make_dbf(
            junk_dbf,
            [(False, "47850100030001-\xc0\xd3-2"), (False, "1111000000100020000")],
        )
        assert read_first_pnu(junk_dbf) == "1111000000100020000", (
            "숫자가 아닌 PNU(지명 텍스트 섞임)는 건너뛰고 다음 유효 레코드를 반환해야 함"
        )

    print("OK: build_region_pnu_seed 파서 self-check 통과")


if __name__ == "__main__":
    main()
