from pathlib import Path

from niwoec.core import Config, fuse, map_requirements, review, scan, verify


def test_scan_map_verify_and_fuse(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("def save():\n    pass\n", encoding="utf-8")
    spec = tmp_path / "spec.txt"
    spec.write_text("save: save data\n", encoding="utf-8")
    tests = tmp_path / "test_app.py"
    tests.write_text("def test_save():  # save\n    assert True\n", encoding="utf-8")
    scanned = scan(source)
    assert len(scanned.findings) == 1
    report = fuse(map_requirements(spec, source), scanned, verify(spec, tests))
    assert report.verdicts[0].satisfied is False


def test_review_empty_input(tmp_path: Path) -> None:
    assert review(tmp_path, Config()).findings == ()
