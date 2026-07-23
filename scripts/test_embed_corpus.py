"""embed_corpus.py의 순수 로직(네트워크/DB 없이) 최소 확인.

사용법: backend/.venv/Scripts/python.exe scripts/test_embed_corpus.py
"""

from embed_corpus import (
    EMBED_DIM,
    FOLDER_TO_CROP_NAME,
    pick_new_or_changed,
    pick_removed,
    validate_embeddings,
)


def test_validate_embeddings_ok() -> None:
    validate_embeddings([[0.0] * EMBED_DIM, [0.0] * EMBED_DIM], expected_count=2)


def test_validate_embeddings_count_mismatch() -> None:
    try:
        validate_embeddings([[0.0] * EMBED_DIM], expected_count=2)
    except RuntimeError:
        return
    raise AssertionError("개수 불일치인데 통과함")


def test_validate_embeddings_dim_mismatch() -> None:
    try:
        validate_embeddings([[0.0] * (EMBED_DIM - 1)], expected_count=1)
    except RuntimeError:
        return
    raise AssertionError("차원 불일치인데 통과함")


def test_folder_to_crop_name_covers_data_dirs() -> None:
    assert set(FOLDER_TO_CROP_NAME) == {"apple", "pear", "cucumber", "potato", "lettuce"}


def test_pick_new_or_changed_skips_unchanged() -> None:
    records = [{"content": "A"}, {"content": "B"}, {"content": "C"}]
    result = pick_new_or_changed(records, existing_contents={"A", "C"})
    assert result == [{"content": "B"}]


def test_pick_removed_finds_gone_content() -> None:
    result = pick_removed(existing_contents={"A", "B", "C"}, current_contents={"A", "C"})
    assert result == {"B"}


if __name__ == "__main__":
    test_validate_embeddings_ok()
    test_validate_embeddings_count_mismatch()
    test_validate_embeddings_dim_mismatch()
    test_folder_to_crop_name_covers_data_dirs()
    test_pick_new_or_changed_skips_unchanged()
    test_pick_removed_finds_gone_content()
    print("OK")
