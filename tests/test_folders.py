from dwi_to_sm import (
    AUTOCONVERT_TEXT,
    autoconvert_folder,
    autoconvert_tree,
    clear_autoconversions,
    find_convertible_folders,
    find_testable_folders,
    is_autoconverted,
    plan_test_tree,
    run_planned_actions,
    scan_folder,
    test_folder,
)


def test_scan_folder_only_returns_dwi_only_folders(dwi_only_song, reference_song):
    assert scan_folder(str(dwi_only_song)) == str(dwi_only_song)
    assert scan_folder(str(reference_song)) is None
    assert scan_folder(str(dwi_only_song / "missing")) is None


def test_find_folders_splits_by_whether_an_sm_exists(tmp_path, dwi_only_song, reference_song):
    assert find_convertible_folders(str(tmp_path)) == [str(dwi_only_song)]
    assert find_testable_folders(str(tmp_path)) == [str(reference_song)]


def test_plan_test_tree_returns_enumerable_comparisons(tmp_path, reference_song):
    plans = plan_test_tree(str(tmp_path))

    assert len(plans) == 1
    assert plans[0].operation == "test"
    assert plans[0].source == str(reference_song / "A.dwi")
    assert plans[0].destination == str(reference_song / "A.sm.converted")
    assert plans[0].accepted is None

    assert run_planned_actions(iter(plans)) == []
    plans[0].accepted = True
    assert run_planned_actions(iter(plans)) == [str(reference_song / "A.sm.converted")]


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


def test_autoconvert_tree_isolates_a_bad_folder(tmp_path, dwi_only_song, bad_dwi_song):
    results = autoconvert_tree(str(tmp_path))

    by_folder = {folder: (written, error) for folder, written, error in results}
    assert by_folder[str(dwi_only_song)] == ([str(dwi_only_song / "B.sm")], None)
    assert by_folder[str(bad_dwi_song)][0] == []
    assert "no DWI tags found" in by_folder[str(bad_dwi_song)][1]
    assert not (bad_dwi_song / "Bad.sm").exists()
    assert not is_autoconverted(str(bad_dwi_song))


def test_test_folder_writes_alongside_the_original(reference_song):
    before = (reference_song / "A.sm").read_bytes()
    written = test_folder(str(reference_song))

    assert written == [str(reference_song / "A.sm.converted")]
    assert (reference_song / "A.sm").read_bytes() == before


def test_autoconverted_folders_are_not_worth_diffing(tmp_path, dwi_only_song, reference_song):
    autoconvert_folder(str(dwi_only_song))

    assert find_testable_folders(str(tmp_path)) == [str(reference_song)]
    assert test_folder(str(dwi_only_song)) == []
    assert not (dwi_only_song / "B.sm.converted").exists()


def test_clear_only_removes_marked_folders(tmp_path, dwi_only_song, reference_song):
    autoconvert_folder(str(dwi_only_song))

    dry = clear_autoconversions(str(tmp_path))
    assert set(dry) == {str(dwi_only_song / "B.sm"), str(dwi_only_song / "autoconvert.txt")}
    assert (dwi_only_song / "B.sm").exists()

    clear_autoconversions(str(tmp_path), dry_run=False)
    assert not (dwi_only_song / "B.sm").exists()
    assert not (dwi_only_song / "autoconvert.txt").exists()
    assert (dwi_only_song / "B.dwi").exists()
    assert (reference_song / "A.sm").exists()
