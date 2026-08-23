"""Unit tests for image dimensions and banner/background classification.

Dimensions are read from the real files in tests/data/images (one per format);
the expected values were cross-checked against Pillow. Classification is pure,
so it is tested on plain Image values without touching the disk.
"""

from pathlib import Path

import pytest

from dwi_to_sm import Image, choose_banner_background, image_size, list_images

IMAGES = Path(__file__).parent / "data" / "images"

# file, width, height
REAL_IMAGES = [
    ("fersure-bn.gif", 410, 128),
    ("fersure-bg.gif", 640, 480),
    ("Gotta Catch Em All-bn.jpg", 416, 164),
    ("Gotta Catch Em All-bg.jpg", 700, 490),
    ("RHYTHM AND POLICE (K.O.G G3 Mix).png", 256, 80),
    ("RHYTHM AND POLICE (K.O.G G3 Mix)-bg.png", 320, 240),
    ("screamaimfire-bn.bmp", 418, 146),
    ("screamaimfire-bg.bmp", 640, 480),
]


@pytest.mark.parametrize(("name", "width", "height"), REAL_IMAGES, ids=[i[0] for i in REAL_IMAGES])
def test_image_size_reads_every_format(name, width, height):
    assert image_size(str(IMAGES / name)) == (width, height)


def test_image_size_returns_none_for_unreadable_files(tmp_path):
    (tmp_path / "truncated.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "garbage.jpg").write_bytes(b"not an image at all")

    assert image_size(str(tmp_path / "truncated.png")) is None
    assert image_size(str(tmp_path / "garbage.jpg")) is None
    assert image_size(str(tmp_path / "missing.png")) is None


@pytest.mark.parametrize(
    ("base", "banner", "background"),
    [
        ("fersure", "fersure-bn.gif", "fersure-bg.gif"),
        ("Gotta Catch Em All", "Gotta Catch Em All-bn.jpg", "Gotta Catch Em All-bg.jpg"),
        (
            "RHYTHM AND POLICE (K.O.G G3 Mix)",
            "RHYTHM AND POLICE (K.O.G G3 Mix).png",
            "RHYTHM AND POLICE (K.O.G G3 Mix)-bg.png",
        ),
        ("screamaimfire", "screamaimfire-bn.bmp", "screamaimfire-bg.bmp"),
    ],
)
def test_real_naming_conventions_are_classified(base, banner, background):
    images = [Image(banner, 410, 128), Image(background, 640, 480)]

    assert choose_banner_background(images, (base,)) == (banner, background)


@pytest.mark.parametrize("name", ["song-bn.png", "song banner.png", "SONG-BN.PNG"])
def test_banner_suffixes(name):
    assert choose_banner_background([Image(name, 999, 999)], ("song",))[0] == name


@pytest.mark.parametrize("name", ["song-bg.png", "song background.png", "SONG-BG.PNG"])
def test_background_suffixes(name):
    assert choose_banner_background([Image(name, 1, 1)], ("song",))[1] == name


def test_a_bare_song_name_is_the_banner():
    assert choose_banner_background([Image("song.png", 1, 1)], ("song",)) == ("song.png", "")


def test_names_beat_dimensions():
    """The suffixes say the opposite of what the shapes suggest; names win."""
    images = [Image("song-bn.png", 640, 480), Image("song-bg.png", 256, 80)]

    assert choose_banner_background(images, ("song",)) == ("song-bn.png", "song-bg.png")


@pytest.mark.parametrize(
    ("width", "height", "is_banner"),
    [
        (256, 80, True),  # classic banner, 3.20
        (410, 128, True),  # 3.20
        (418, 146, True),  # 2.86
        (416, 164, True),  # 2.54
        (512, 256, True),  # exactly at the 2.0 threshold
        (700, 490, False),  # 1.43
        (640, 480, False),  # 4:3
        (320, 240, False),  # 4:3
        (1280, 720, False),  # 16:9, 1.78
    ],
)
def test_aspect_ratio_decides_when_names_say_nothing(width, height, is_banner):
    banner, background = choose_banner_background([Image("x.png", width, height)])

    assert (banner == "x.png") is is_banner
    assert (background == "x.png") is not is_banner


def test_the_narrowest_wide_image_is_the_banner():
    images = [Image("big.png", 1024, 320), Image("small.png", 256, 80)]

    assert choose_banner_background(images)[0] == "small.png"


def test_the_largest_remaining_image_is_the_background():
    images = [Image("small.png", 320, 240), Image("big.png", 640, 480)]

    assert choose_banner_background(images)[1] == "big.png"


def test_file_size_breaks_an_area_tie():
    images = [Image("thin.png", 640, 480, bytes=1000), Image("fat.png", 640, 480, bytes=90000)]

    assert choose_banner_background(images)[1] == "fat.png"


def test_one_image_is_never_used_twice():
    assert choose_banner_background([Image("only.png", 256, 80)]) == ("only.png", "")


@pytest.mark.parametrize("name", ["cdtitle.png", "jacket.png", "disc.png", "cdimage.png"])
def test_non_song_art_is_ignored(name):
    assert choose_banner_background([Image(name, 256, 80)]) == ("", "")


def test_no_images_at_all():
    assert choose_banner_background([]) == ("", "")


def test_explicit_banner_does_not_block_background_selection():
    images = [Image("song.png", 256, 80), Image("song-bg.png", 640, 480)]

    assert choose_banner_background(images, ("song",), need_banner=False) == ("", "song-bg.png")


def test_list_images_returns_all_readable_supported_images(tmp_path):
    (tmp_path / "banner.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (256).to_bytes(4, "big") + (80).to_bytes(4, "big")
    )
    (tmp_path / "notes.txt").write_text("not an image")

    assert [image.name for image in list_images(str(tmp_path))] == ["banner.png"]
