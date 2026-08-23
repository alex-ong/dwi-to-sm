"""Banner/background detection.

DWI has no tags for either image, so they are guessed from the song folder:
filename hints first, then the image dimensions read straight from the file
headers (no image library needed).
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "Image",
    "choose_banner_background",
    "image_size",
    "list_images",
    "pick_banner_background",
]

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif")
# Banners are wide strips (256x80, 512x160); backgrounds are 4:3 or 16:9.
BANNER_RATIO = 2.0
_SKIP_HINTS = ("cdtitle", "jacket", "cdimage", "disc")


def image_size(path: str) -> tuple[int, int] | None:
    """Read width/height straight from the file header."""
    try:
        with Path(path).open("rb") as handle:
            head = handle.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
                return struct.unpack(">II", head[16:24])
            if head[:6] in (b"GIF87a", b"GIF89a"):
                return struct.unpack("<HH", head[6:10])
            if head[:2] == b"BM":
                width, height = struct.unpack("<ii", head[18:26])
                return abs(width), abs(height)
            if head[:2] == b"\xff\xd8":
                handle.seek(2)
                while True:
                    marker = handle.read(2)
                    if len(marker) < 2 or marker[0] != 0xFF:
                        return None
                    length = struct.unpack(">H", handle.read(2))[0]
                    # SOF0..SOF15, excluding the non-frame DHT/JPG/DAC markers.
                    if 0xC0 <= marker[1] <= 0xCF and marker[1] not in (0xC4, 0xC8, 0xCC):
                        body = handle.read(5)
                        height, width = struct.unpack(">HH", body[1:5])
                        return width, height
                    handle.seek(length - 2, 1)
    except OSError, struct.error, IndexError:
        return None
    return None


@dataclass(frozen=True)
class Image:
    name: str
    width: int
    height: int
    bytes: int = 0

    @property
    def ratio(self) -> float:
        return self.width / self.height if self.height else 0.0

    @property
    def area(self) -> int:
        return self.width * self.height


def list_images(directory: str) -> list[Image]:
    """List every readable supported image file in a song directory."""
    if not directory or not Path(directory).is_dir():
        return []
    try:
        entries = sorted(path.name for path in Path(directory).iterdir())
    except OSError:
        return []

    images: list[Image] = []
    for name in entries:
        if not name.lower().endswith(IMAGE_EXTS):
            continue
        path = Path(directory) / name
        size = image_size(path)
        if size is None:
            continue
        try:
            on_disk = path.stat().st_size
        except OSError:
            on_disk = 0
        images.append(Image(name, size[0], size[1], on_disk))
    return images


def _classify_by_name(name: str, bases: Sequence[str]) -> str | None:
    stem = Path(name).stem.lower()
    for base in bases:
        base = base.lower()
        if not base:
            continue
        if stem == base:
            return "banner"
        suffix = stem[len(base) :].strip(" -_") if stem.startswith(base) else ""
        if suffix in ("bg", "background"):
            return "background"
        if suffix in ("bn", "banner"):
            return "banner"
    if "background" in stem or stem.endswith(("-bg", " bg", "_bg")):
        return "background"
    if "banner" in stem or stem.endswith(("-bn", " bn", "_bn")):
        return "banner"
    return None


def choose_banner_background(
    images: Sequence[Image],
    bases: Sequence[str] = (),
    need_banner: bool = True,
    need_background: bool = True,
) -> tuple[str, str]:
    """Pick the banner and background out of a song's images.

    ``bases`` are name stems to match against, usually the song title and the
    simfile's filename.
    """
    banner = background = ""
    unknown: list[Image] = []
    for image in images:
        if any(hint in image.name.lower() for hint in _SKIP_HINTS):
            continue
        kind = _classify_by_name(image.name, bases)
        if kind == "banner" and need_banner and not banner:
            banner = image.name
        elif kind == "background" and need_background and not background:
            background = image.name
        elif kind is None:
            unknown.append(image)

    if need_banner and not banner:
        wide = [i for i in unknown if i.ratio >= BANNER_RATIO]
        if wide:
            banner = min(wide, key=lambda i: i.area).name
    if need_background and not background:
        rest = [i for i in unknown if i.name != banner and i.ratio < BANNER_RATIO]
        if rest:
            background = max(rest, key=lambda i: (i.area, i.bytes)).name
    return banner, background


def pick_banner_background(directory: str, bases: Sequence[str]) -> tuple[str, str]:
    """Guess the banner and background filenames in a song folder."""
    return choose_banner_background(list_images(directory), bases)
