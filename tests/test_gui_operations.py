"""A bad song must not stop the GUI worker from converting the rest of the library."""

from dwi_to_sm.gui.models import BarCounts, SongEntry
from dwi_to_sm.gui.operations import execute


def _entry(folder, dwi_name):
    return SongEntry(
        folder=folder,
        pack="pack",
        dwi_files=[dwi_name],
        sm_files=[],
        generated_files=[],
        autoconverted=False,
        action="convert",
    )


def test_execute_continues_past_a_bad_song(dwi_only_song, bad_dwi_song):
    bad = _entry(bad_dwi_song, "Bad.dwi")
    good = _entry(dwi_only_song, "B.dwi")

    progresses = list(execute([bad, good]))

    assert (dwi_only_song / "B.sm").exists()
    assert good.error is None
    assert good.autoconverted is True

    assert not (bad_dwi_song / "Bad.sm").exists()
    assert bad.error is not None
    assert "no DWI tags found" in bad.error
    assert bad.autoconverted is False
    assert not (bad_dwi_song / "autoconvert.txt").exists()

    failures = [p for p in progresses if p.error is not None]
    assert len(failures) == 1
    assert failures[0].folder == bad_dwi_song
    assert "FAILED Bad.dwi" in failures[0].message


def test_execute_reports_progress_for_every_operation(dwi_only_song, bad_dwi_song):
    bad = _entry(bad_dwi_song, "Bad.dwi")
    good = _entry(dwi_only_song, "B.dwi")

    progresses = list(execute([bad, good]))

    # one convert + one mark per entry
    assert len(progresses) == 4
    assert [p.completed for p in progresses] == [1, 2, 3, 4]
    assert all(p.total == 4 for p in progresses)


def test_entry_counts_reflect_pass_fail_and_pending(dwi_only_song, bad_dwi_song):
    bad = _entry(bad_dwi_song, "Bad.dwi")
    good = _entry(dwi_only_song, "B.dwi")
    untouched = _entry(dwi_only_song, "C.dwi")

    assert bad.counts == BarCounts(total=1)
    assert good.counts == BarCounts(total=1)

    list(execute([bad, good]))

    assert bad.counts == BarCounts(total=1, failed=1)
    assert good.counts == BarCounts(total=1, passed=1)
    assert untouched.counts == BarCounts(total=1)


def test_entry_counts_mark_pre_existing_conversions_as_no_op(dwi_only_song):
    entry = SongEntry(
        folder=dwi_only_song,
        pack="pack",
        dwi_files=["B.dwi"],
        sm_files=["B.sm"],
        generated_files=[],
        autoconverted=True,
        already_converted=["B.sm"],
    )

    assert entry.counts == BarCounts(total=1, no_op=1)


def test_entry_counts_treat_action_none_as_instantly_done(dwi_only_song):
    entry = _entry(dwi_only_song, "B.dwi")
    entry.action = "none"

    assert entry.counts == BarCounts(total=1, no_op=1)


def test_bar_counts_add_combines_totals():
    assert BarCounts(total=2, passed=1) + BarCounts(total=3, failed=1) == BarCounts(
        total=5, passed=1, failed=1
    )
