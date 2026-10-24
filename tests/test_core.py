from pathlib import Path

from niwoec.core import Config, fuse, map_requirements, online, review, scan, verify


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


def test_scan_ignores_click_style_group_with_child_command(tmp_path: Path) -> None:
    source = tmp_path / "cli.py"
    source.write_text(
        """
import click

@click.group()
def model():
    \"\"\"Manage local models.\"\"\"

@model.command()
def list_models():
    return 1
""",
        encoding="utf-8",
    )
    assert scan(source).findings == ()


def test_scan_keeps_ordinary_docstring_placeholder(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text('def unfinished():\n    """Not implemented yet."""\n', encoding="utf-8")
    assert len(scan(source).findings) == 1


def test_online_detects_urls_and_api_calls_without_network(tmp_path: Path) -> None:
    source = tmp_path / "client.py"
    source.write_text(
        'import requests\n\nrequests.get("https://example.test/api")\n',
        encoding="utf-8",
    )
    findings = online(source).findings
    assert {finding.rule_id for finding in findings} == {"external-url", "network-call"}
