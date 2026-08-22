from dwi_to_sm import (
    AUTOCONVERT_TEXT,
    autoconvert_folder,
    autoconvert_tree,
    clear_autoconversions,
    find_convertible_folders,
    find_testable_folders,
    is_autoconverted,
    scan_folder,
    test_folder,
)


def test_scan_folder_only_returns_dwi_only_folders(dwi_only_song, reference_song):
    assert scan_folder(str(dwi_only_song)) == str(dwi_only_song)
    assert scan_folder(str(reference_song)) is None
    assert scan_folder(str(dwi_only_song / "missing")) is None


def test_find_folders_splits_by_whether_an_sm_exists(tmp_path, dwi_only_song,
                                                     reference_song):
    assert find_convertible_folders(str(tmp_path)) == [str(dwi_only_song)]
    assert find_testable_folders(str(tmp_path)) == [str(reference_song)]


def test_autoconvert_writes_sm_and_marker(dwi_only_song):
    written = autoconvert_folder(str(dwi_only_song))

    assert written == [str(dwi_only_song / "B.sm")]
    assert (dwi_only_song / "B.sm").exists()
    assert (dwi_only_song / "autoconvert.txt").read_text() == AUTOCONVERT_TEXT
    assert is_autoconverted(str(dwi_only_song))


def test_autoconvert_is_idempotent(dwi_only_song):
    autoconvert_folder(str(dwi_only_song))
    first = (dwi_only_song / "B.sm").read_text(encoding="utf-8")

    assert autoconvert_folder(str(dwi_only_song)) == []
    assert (dwi_only_song / "B.sm").read_text(encoding="utf-8") == first


def test_autoconvert_never_touches_hand_made_sm(reference_song):
    before = (reference_song / "A.sm").read_bytes()

    assert autoconvert_folder(str(reference_song)) == []
    assert (reference_song / "A.sm").read_bytes() == before
    assert not is_autoconverted(str(reference_song))


def test_autoconvert_tree_reports_each_folder(tmp_path, dwi_only_song, reference_song):
    results = autoconvert_tree(str(tmp_path))

    assert results == [(str(dwi_only_song), [str(dwi_only_song / "B.sm")], None)]


def test_test_folder_writes_alongside_the_original(reference_song):
    before = (reference_song / "A.sm").read_bytes()
    written = test_folder(str(reference_song))

    assert written == [str(reference_song / "A.sm.converted")]
    assert (reference_song / "A.sm").read_bytes() == before


def test_clear_only_removes_marked_folders(tmp_path, dwi_only_song, reference_song):
    autoconvert_folder(str(dwi_only_song))

    dry = clear_autoconversions(str(tmp_path))
    assert set(dry) == {str(dwi_only_song / "B.sm"),
                        str(dwi_only_song / "autoconvert.txt")}
    assert (dwi_only_song / "B.sm").exists()

    clear_autoconversions(str(tmp_path), dry_run=False)
    assert not (dwi_only_song / "B.sm").exists()
    assert not (dwi_only_song / "autoconvert.txt").exists()
    assert (dwi_only_song / "B.dwi").exists()
    assert (reference_song / "A.sm").exists()
