from dwi_to_sm import image_size, pick_banner_background


def test_image_size_reads_png_header(tmp_path, write_png):
    assert image_size(str(write_png(tmp_path / "x.png", 256, 80))) == (256, 80)
    assert image_size(str(tmp_path / "missing.png")) is None


def test_aspect_ratio_decides_banner_versus_background(tmp_path, write_png):
    write_png(tmp_path / "one.png", 256, 80)
    write_png(tmp_path / "two.png", 640, 480)

    assert pick_banner_background(str(tmp_path), ()) == ("one.png", "two.png")


def test_filename_hints_win_over_dimensions(tmp_path, write_png):
    write_png(tmp_path / "song.png", 640, 480)
    write_png(tmp_path / "song-bg.png", 256, 80)

    assert pick_banner_background(str(tmp_path), ("song",)) == ("song.png", "song-bg.png")


def test_cdtitle_is_ignored(tmp_path, write_png):
    write_png(tmp_path / "cdtitle.png", 512, 160)
    write_png(tmp_path / "art.png", 640, 480)

    assert pick_banner_background(str(tmp_path), ()) == ("", "art.png")


def test_missing_folder_yields_no_images():
    assert pick_banner_background("", ()) == ("", "")
