from pathlib import Path

from niwoec.core import scan, render


def test_json_output_is_stable(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("def f():\n    pass\n", encoding="utf-8")
    output = render(scan(source), "json")
    assert '"rule_id": "stub-function"' in output
