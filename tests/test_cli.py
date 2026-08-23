from dwi_to_sm.cli import main


def test_cli_converts_a_single_file(tmp_path, reference_song, capsys):
    out = tmp_path / "out.sm"

    assert main([str(reference_song / "A.dwi"), "-o", str(out)]) == 0
    assert out.exists()
    assert "OK" in capsys.readouterr().out


def test_cli_never_overwrites_an_existing_sm(reference_song, capsys):
    before = (reference_song / "A.sm").read_bytes()

    assert main([str(reference_song / "A.dwi")]) == 0
    assert (reference_song / "A.sm").read_bytes() == before
    assert "SKIP" in capsys.readouterr().out


def test_cli_force_allows_overwriting(reference_song):
    before = (reference_song / "A.sm").read_bytes()

    assert main([str(reference_song / "A.dwi"), "--force"]) == 0
    assert (reference_song / "A.sm").read_bytes() != before


def test_cli_folder_run_leaves_folders_with_an_sm_alone(tmp_path, dwi_only_song, reference_song):
    before = (reference_song / "A.sm").read_bytes()

    assert main([str(tmp_path)]) == 0
    assert (dwi_only_song / "B.sm").exists()
    assert (dwi_only_song / "autoconvert.txt").exists()
    assert (reference_song / "A.sm").read_bytes() == before
    assert not (reference_song / "autoconvert.txt").exists()


def test_cli_test_mode_writes_converted_files(tmp_path, reference_song):
    assert main([str(tmp_path), "--test"]) == 0
    assert (reference_song / "A.sm.converted").exists()


def test_cli_dry_run_test_mode_reports_songs_without_writing(tmp_path, reference_song, capsys):
    assert main([str(tmp_path), "--test", "--dry-run"]) == 0

    output = capsys.readouterr().out
    assert "1 song(s) have both .dwi and .sm files" in output
    assert "1 .dwi file(s) would be compared" in output
    assert f"DRY  {reference_song}" in output
    assert "     A.dwi -> A.sm.converted" in output
    assert not (reference_song / "A.sm.converted").exists()


def test_cli_test_mode_ignores_autoconverted_folders(tmp_path, dwi_only_song):
    main([str(tmp_path)])

    assert main([str(tmp_path), "--test"]) == 0
    assert not (dwi_only_song / "B.sm.converted").exists()


def test_cli_clear_removes_autoconversions(tmp_path, dwi_only_song):
    main([str(tmp_path)])

    assert main([str(tmp_path), "--clear-autoconversions"]) == 0
    assert not (dwi_only_song / "B.sm").exists()


def test_cli_clear_test_outputs(tmp_path, reference_song, capsys):
    output = reference_song / "A.sm.converted"
    output.write_text("generated")

    assert main([str(tmp_path), "--clear-test-outputs", "--dry-run"]) == 0
    assert output.exists()
    assert "DRY" in capsys.readouterr().out

    assert main([str(tmp_path), "--clear-test-outputs"]) == 0
    assert not output.exists()


def test_cli_reports_failure_for_a_bad_file(tmp_path, capsys):
    bad = tmp_path / "bad.dwi"
    bad.write_text("not a simfile")

    assert main([str(bad)]) == 1
    assert "FAIL" in capsys.readouterr().out
