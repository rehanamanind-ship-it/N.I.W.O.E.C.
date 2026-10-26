from pathlib import Path
import pytest

from niwoec.core import (
    Config,
    InputError,
    enforce_coverage,
    dynamic_test,
    deep_test,
    fuse,
    map_requirements,
    online,
    parse,
    report_data,
    review,
    render,
    scan,
    verify,
)


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


def test_verdict_separates_mapping_testing_and_satisfaction(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("def load_model():\n    return 1\n", encoding="utf-8")
    spec = tmp_path / "spec.txt"
    spec.write_text("load_model: load a model\nsave: save data\n", encoding="utf-8")
    tests = tmp_path / "test_app.py"
    tests.write_text(
        'def test_load_model_behavior():\n    """Covers load_model."""\n    assert True\n',
        encoding="utf-8",
    )
    report = fuse(map_requirements(spec, source), scan(source), verify(spec, tests))
    load, save = report.verdicts
    assert (load.mapped, load.tested, load.satisfied) == (True, True, True)
    assert (save.mapped, save.tested, save.satisfied) == (False, False, False)
    assert (load.status, save.status) == ("satisfied", "unverified")
    assert "Suggested test name: test_save_..." in save.guidance


def test_coverage_threshold_reads_cobertura_report(tmp_path: Path) -> None:
    report = tmp_path / "coverage.xml"
    report.write_text('<coverage line-rate="1.0" />', encoding="utf-8")
    enforce_coverage(100, report)


def test_coverage_threshold_rejects_missing_invalid_and_low_reports(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="not found"):
        enforce_coverage(80, tmp_path / "missing.xml")
    report = tmp_path / "coverage.xml"
    report.write_text("<coverage>", encoding="utf-8")
    with pytest.raises(InputError, match="invalid"):
        enforce_coverage(80, report)
    report.write_text('<coverage line-rate="0.5" />', encoding="utf-8")
    with pytest.raises(InputError, match="below"):
        enforce_coverage(80, report)


def test_parse_rejects_malformed_python(tmp_path: Path) -> None:
    source = tmp_path / "broken.py"
    source.write_text("def broken(:\n", encoding="utf-8")
    with pytest.raises(InputError, match="cannot parse"):
        parse(source)


def test_scan_detects_all_placeholder_forms(tmp_path: Path) -> None:
    source = tmp_path / "placeholders.py"
    source.write_text(
        """
def empty():
    \"\"\"Documentation only.\"\"\"

def passing():
    pass

def missing():
    raise NotImplementedError()

def none_value():
    return None
""",
        encoding="utf-8",
    )
    assert len(scan(source).findings) == 4


def test_scan_detects_group_add_command_and_ignores_async_group(tmp_path: Path) -> None:
    source = tmp_path / "groups.py"
    source.write_text(
        """
import click

@click.group
def cli():
    \"\"\"Root command.\"\"\"

@cli.command
async def child():
    return 1

cli.add_command(child)
""",
        encoding="utf-8",
    )
    assert scan(source).findings == ()


def test_scan_keeps_group_without_children_as_placeholder(tmp_path: Path) -> None:
    source = tmp_path / "group.py"
    source.write_text(
        '@cli.group()\ndef cli():\n    """No registered children."""\n',
        encoding="utf-8",
    )
    assert len(scan(source).findings) == 1


def test_map_uses_description_tokens_when_identifier_is_absent(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("def create_report():\n    return 1\n", encoding="utf-8")
    spec = tmp_path / "spec.txt"
    spec.write_text("reporting: create report\nignored line\n", encoding="utf-8")
    report = map_requirements(spec, source)
    assert report.requirements == ("reporting",)
    assert report.links


def test_review_reports_long_functions_and_urls(tmp_path: Path) -> None:
    source = tmp_path / "long.py"
    source.write_text(
        "def long():\n"
        + "".join("    value = 1\n" for _ in range(4))
        + '    return "https://example.test"\n',
        encoding="utf-8",
    )
    rules = review(source, Config(max_function_lines=2)).findings
    assert {item.rule_id for item in rules} == {"long-function", "external-url"}


def test_verify_finds_marker_and_decorator_references(tmp_path: Path) -> None:
    spec = tmp_path / "spec.txt"
    spec.write_text("load_model: load model\nsave: save data\n", encoding="utf-8")
    tests = tmp_path / "test_app.py"
    tests.write_text(
        '@marker(requirement="load_model")\n'
        "def unrelated():\n"
        '    """save behavior."""\n'
        "    assert True\n",
        encoding="utf-8",
    )
    assert verify(spec, tests).pinned == ("load_model", "save")


def test_render_supports_all_formats(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("def save():\n    pass\n", encoding="utf-8")
    report = scan(source)
    assert "stub-function" in render(report, "text")
    assert "stub-function" in render(report, "markdown")
    assert '"runs"' in render(report, "sarif")


def test_render_verdict_markdown_includes_guidance(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("def save():\n    return 1\n", encoding="utf-8")
    spec = tmp_path / "spec.txt"
    spec.write_text("save: save data\n", encoding="utf-8")
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    result = fuse(map_requirements(spec, source), scan(source), verify(spec, test_dir))
    output = render(result, "markdown")
    assert "Requirement | Mapped | Tested | Status | Findings" in output
    assert "Suggested test name: test_save_..." in output


def test_dynamic_test_runs_bounded_local_suite(tmp_path: Path) -> None:
    tests = tmp_path / "test_dynamic.py"
    tests.write_text("def test_dynamic_passes():\n    assert 2 + 2 == 4\n", encoding="utf-8")
    report = dynamic_test(tests, tmp_path)
    assert (report.status, report.passed, report.failed) == ("passed", 1, 0)


def test_deep_test_kills_mutant_with_behavioral_test(tmp_path: Path) -> None:
    source = tmp_path / "deep_subject.py"
    source.write_text("def add(left, right):\n    return left + right\n", encoding="utf-8")
    tests = tmp_path / "test_deep_subject.py"
    tests.write_text(
        "from deep_subject import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    report = deep_test(source, tests, tmp_path, max_mutants=1)
    assert report.baseline.status == "passed"
    assert report.mutants == 1
    assert report.killed == 1


def test_report_data_rejects_unknown_report() -> None:
    with pytest.raises(TypeError, match="unsupported"):
        report_data(object())


def test_map_and_verify_report_input_errors(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="specification"):
        map_requirements(tmp_path / "missing.frs", tmp_path)
    with pytest.raises(InputError, match="verification"):
        verify(tmp_path / "missing.frs", tmp_path)
