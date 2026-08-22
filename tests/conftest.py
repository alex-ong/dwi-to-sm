import shutil
import struct
import zlib
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


@pytest.fixture
def write_png():
    def _write(path: Path, width: int, height: int) -> Path:
        header = b"IHDR" + struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + struct.pack(">I", 13) + header + struct.pack(">I", zlib.crc32(header))
        )
        return path
    return _write
