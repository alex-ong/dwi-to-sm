import shutil
from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data"


@pytest.fixture
def reference_song(tmp_path):
    """A copy of the reference song folder (A.dwi + A.sm + images)."""
    dest = tmp_path / "A"
    shutil.copytree(DATA / "A", dest)
    return dest


@pytest.fixture
def dwi_only_song(tmp_path):
    """A song folder holding only a .dwi."""
    dest = tmp_path / "B"
    dest.mkdir()
    shutil.copy(DATA / "A" / "A.dwi", dest / "B.dwi")
    return dest
