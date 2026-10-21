import subprocess
import sys
from pathlib import Path

from niwoec.cli import main


def test_help_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "niwoec.cli", "help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "check" in result.stdout


def test_version_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "niwoec.cli", "--version"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "1.0.0"


def test_cli_commands(tmp_path: Path, capsys: object) -> None:
    source = tmp_path / "app.py"
    source.write_text("def save():\n    return 1\n", encoding="utf-8")
    spec = tmp_path / "spec.txt"
    spec.write_text("save: save data\n", encoding="utf-8")
    tests = tmp_path / "test_app.py"
    tests.write_text("# save\n", encoding="utf-8")
    assert main(["scan", str(source), "--format", "json"]) == 0
    assert main(["review", str(source)]) == 0
    assert main(["map", str(spec), str(source)]) == 0
    assert main(["verify", str(spec), str(tests)]) == 0
    assert main(["check", str(spec), str(source), "--tests", str(tests)]) == 0
    assert main(["stubs", str(source)]) == 0
    assert main(["help"]) == 0
    assert main(["scan", str(tmp_path / "missing.py")]) == 2
    assert capsys.readouterr().out
