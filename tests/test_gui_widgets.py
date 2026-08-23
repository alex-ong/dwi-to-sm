"""Hover text for the conversion bars: per-segment for songs, a breakdown for folders."""

from dwi_to_sm.gui.models import BarCounts
from dwi_to_sm.gui.widgets import segment_tooltip, summary_tooltip


def test_segment_tooltip_identifies_the_segment_under_the_cursor():
    counts = BarCounts(total=2, passed=1, failed=1)

    assert segment_tooltip(counts, 0, 100) == "Converted"
    assert segment_tooltip(counts, 99, 100) == "Conversion attempt failed"


def test_segment_tooltip_reports_no_op_and_not_done():
    counts = BarCounts(total=4, passed=1, no_op=1, failed=1)

    assert segment_tooltip(counts, 30, 100) == "No conversion required"
    assert segment_tooltip(counts, 90, 100) == "Not converted yet"


def test_segment_tooltip_is_empty_for_an_empty_bar():
    assert segment_tooltip(BarCounts(total=0), 0, 100) == ""
    assert segment_tooltip(BarCounts(total=1), 0, 0) == ""


def test_summary_tooltip_lists_every_count():
    counts = BarCounts(total=5, passed=3, no_op=2, failed=0)

    assert summary_tooltip(counts) == (
        "Converted: 3\nNo conversion required: 2\nFailed: 0"
    )
