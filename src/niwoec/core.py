"""Small typed contracts and analysis functions for niwoec."""

import ast
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class NiwoecError(Exception):
    """Base class for expected user-facing errors."""


class InputError(NiwoecError):
    """Invalid or unreadable input."""


def enforce_coverage(minimum: float, report_path: Path = Path("coverage.xml")) -> None:
    """Require a Cobertura XML report to meet the requested line coverage."""
    if not report_path.is_file():
        raise InputError(f"coverage report not found: {report_path}")
    try:
        root = ET.parse(report_path).getroot()
        covered = float(root.attrib["line-rate"]) * 100
    except (ET.ParseError, KeyError, TypeError, ValueError) as exc:
        raise InputError(f"invalid coverage report: {report_path}") from exc
    if covered < minimum:
        raise InputError(f"coverage {covered:.2f}% is below required {minimum:.2f}%")


@dataclass(frozen=True)
class Config:
    """Runtime thresholds."""

    max_function_lines: int = 40
    untested_severity: str = "warning"


_NETWORK_CALLS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "request",
    "urlopen",
    "fetch",
}


@dataclass(frozen=True)
class Finding:
    """A deterministic source-code finding."""

    finding_id: str
    rule_id: str
    severity: str
    message: str
    file: str
    line: int


@dataclass(frozen=True)
class ScanReport:
    """Placeholder-function findings."""

    findings: tuple[Finding, ...]


@dataclass(frozen=True)
class MapReport:
    """Requirement-to-file links."""

    links: tuple[tuple[str, str], ...]
    requirements: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifyReport:
    """Requirements referenced by tests."""

    pinned: tuple[str, ...]


@dataclass(frozen=True)
class ReviewReport:
    """Maintainability findings."""

    findings: tuple[Finding, ...]


@dataclass(frozen=True)
class Verdict:
    """One requirement's result."""

    requirement_id: str
    mapped: bool
    tested: bool
    satisfied: bool
    severity: str
    guidance: str
    findings: tuple[str, ...]


@dataclass(frozen=True)
class VerdictReport:
    """Combined verification result."""

    verdicts: tuple[Verdict, ...]


def stable_id(rule_id: str, language: str, node: ast.AST) -> str:
    """Create the stable twelve-character finding ID."""
    normalized = ast.dump(node, annotate_fields=True, include_attributes=False)
    return hashlib.sha1(f"{rule_id}{language}{normalized}".encode()).hexdigest()[:12]


def parse(path: Path) -> ast.Module:
    """Parse one Python file."""
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise InputError(f"cannot parse {path}: {exc}") from exc


def _files(path: Path) -> list[Path]:
    return sorted(path.rglob("*.py")) if path.is_dir() else [path]


def _is_group_decorator(decorator: ast.expr) -> bool:
    """Return whether a decorator is a qualified group registration."""
    expression = decorator.func if isinstance(decorator, ast.Call) else decorator
    return isinstance(expression, ast.Attribute) and expression.attr == "group"


def _has_child_command(tree: ast.Module, group_name: str) -> bool:
    """Check whether a group callback has statically registered child commands."""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name == group_name:
            continue
        for decorator in node.decorator_list:
            expression = decorator.func if isinstance(decorator, ast.Call) else decorator
            if (
                isinstance(expression, ast.Attribute)
                and isinstance(expression.value, ast.Name)
                and expression.value.id == group_name
                and expression.attr in {"command", "group"}
            ):
                return True
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == group_name
            and node.func.attr == "add_command"
        ):
            return True
    return False


def _stub(node: ast.FunctionDef | ast.AsyncFunctionDef, tree: ast.Module) -> bool:
    """Return whether a function is an unfinished non-registration callback."""
    if any(
        _is_group_decorator(decorator) for decorator in node.decorator_list
    ) and _has_child_command(tree, node.name):
        return False
    body = [
        item
        for item in node.body
        if not (
            isinstance(item, ast.Expr)
            and isinstance(item.value, ast.Constant)
            and isinstance(item.value.value, str)
        )
    ]
    if not body or isinstance(body[0], ast.Pass):
        return True
    if len(body) == 1 and isinstance(body[0], ast.Raise) and isinstance(body[0].exc, ast.Call):
        return (
            isinstance(body[0].exc.func, ast.Name) and body[0].exc.func.id == "NotImplementedError"
        )
    return (
        len(body) == 1
        and isinstance(body[0], ast.Return)
        and (
            body[0].value is None
            or isinstance(body[0].value, ast.Constant)
            and body[0].value.value is None
        )
    )


def scan(path: Path) -> ScanReport:
    """Find empty and placeholder functions."""
    findings: list[Finding] = []
    for file in _files(path):
        tree = parse(file)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _stub(node, tree):
                findings.append(
                    Finding(
                        stable_id("stub-function", "python", node),
                        "stub-function",
                        "high",
                        f"Function {node.name} is a placeholder",
                        str(file),
                        node.lineno,
                    )
                )
    return ScanReport(
        tuple(sorted(findings, key=lambda item: (item.file, item.line, item.finding_id)))
    )


def map_requirements(spec: Path, source: Path) -> MapReport:
    """Link `id: description` requirements to source files."""
    try:
        lines = spec.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise InputError(f"cannot read specification {spec}: {exc}") from exc
    links: list[tuple[str, str]] = []
    for line in lines:
        match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*:\s*(.+)$", line)
        if match:
            tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", f"{match[1]} {match[2]}".lower()))
            files = [(file, file.read_text(encoding="utf-8").lower()) for file in _files(source)]
            identifier_matches = [
                (file, content) for file, content in files if match[1].lower() in content
            ]
            candidates = identifier_matches or files
            for file, content in candidates:
                if identifier_matches or any(token in content for token in tokens):
                    links.append((match[1], str(file)))
    requirement_ids = tuple(
        match.group(1)
        for line in lines
        if (match := re.match(r"^\s*([A-Za-z0-9_.-]+)\s*:\s*(.+)$", line))
    )
    return MapReport(tuple(sorted(set(links))), requirement_ids)


def verify(spec: Path, tests: Path) -> VerifyReport:
    """Find requirement references in test names, docs, decorators, and markers."""
    try:
        requirements = [
            line.split(":", 1)[0].strip()
            for line in spec.read_text(encoding="utf-8").splitlines()
            if ":" in line
        ]
        pinned: set[str] = set()
        for file in _files(tests):
            content = file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file))
            for requirement in requirements:
                if re.search(rf"\btest_{re.escape(requirement)}\b", content):
                    pinned.add(requirement)
                if re.search(rf"#\s*{re.escape(requirement)}\b", content):
                    pinned.add(requirement)
                if re.search(
                    rf"(?:requirement|frs)\s*[:=(]\s*[\"']{re.escape(requirement)}", content, re.I
                ):
                    pinned.add(requirement)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        docstring = ast.get_docstring(node) or ""
                        if requirement in node.name or requirement in docstring:
                            pinned.add(requirement)
                        if any(
                            requirement in ast.dump(decorator) for decorator in node.decorator_list
                        ):
                            pinned.add(requirement)
    except (OSError, UnicodeError) as exc:
        raise InputError(f"cannot read verification input: {exc}") from exc
    return VerifyReport(tuple(item for item in requirements if item in pinned))


def review(path: Path, config: Config) -> ReviewReport:
    """Find long functions and declared online dependencies."""
    findings: list[Finding] = []
    for file in _files(path):
        tree = parse(file)
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.end_lineno
                and node.end_lineno - node.lineno + 1 > config.max_function_lines
            ):
                findings.append(
                    Finding(
                        stable_id("long-function", "python", node),
                        "long-function",
                        "medium",
                        f"Function {node.name} exceeds the line threshold",
                        str(file),
                        node.lineno,
                    )
                )
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if re.search(r"https?://[^\s\"']+", node.value):
                    findings.append(
                        Finding(
                            stable_id("external-url", "python", node),
                            "external-url",
                            "low",
                            "External URL requires an offline contract or integration test",
                            str(file),
                            node.lineno,
                        )
                    )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _NETWORK_CALLS
            ):
                findings.append(
                    Finding(
                        stable_id("network-call", "python", node),
                        "network-call",
                        "low",
                        "Network/API call detected; validate it with an offline contract or integration test",
                        str(file),
                        node.lineno,
                    )
                )
    return ReviewReport(
        tuple(sorted(findings, key=lambda item: (item.file, item.line, item.finding_id)))
    )


def online(path: Path) -> ReviewReport:
    """Report URLs and network/API calls without contacting the network."""
    return review(path, Config(max_function_lines=2**31 - 1))


def fuse(
    mapped: MapReport,
    scanned: ScanReport,
    verified: VerifyReport,
    config: Config | None = None,
) -> VerdictReport:
    """Combine reports into independent mapping, testing, and satisfaction states."""
    settings = config or Config()
    requirements = sorted(
        set(mapped.requirements) | {item for item, _ in mapped.links} | set(verified.pinned)
    )
    verdicts = []
    for requirement in requirements:
        files = {file for item, file in mapped.links if item == requirement}
        findings = tuple(item.finding_id for item in scanned.findings if item.file in files)
        mapped_state = bool(files)
        tested_state = requirement in verified.pinned
        guidance = (
            ""
            if tested_state
            else f"Missing behavioral test reference: {requirement}; "
            f"Suggested test name: test_{requirement}_..."
        )
        verdicts.append(
            Verdict(
                requirement,
                mapped_state,
                tested_state,
                bool(mapped_state and tested_state and not findings),
                "" if tested_state else settings.untested_severity,
                guidance,
                findings,
            )
        )
    return VerdictReport(tuple(verdicts))


def report_data(report: Any) -> dict[str, Any]:
    """Convert a report to JSON-compatible data."""
    if isinstance(report, (ScanReport, ReviewReport)):
        return {"findings": [item.__dict__ for item in report.findings]}
    if isinstance(report, MapReport):
        return {"links": [{"requirement_id": a, "file": b} for a, b in report.links]}
    if isinstance(report, VerifyReport):
        return {"pinned": list(report.pinned)}
    if isinstance(report, VerdictReport):
        mapped = sum(item.mapped for item in report.verdicts)
        tested = sum(item.tested for item in report.verdicts)
        satisfied = sum(item.satisfied for item in report.verdicts)
        return {
            "summary": {
                "mapped": mapped,
                "tested": tested,
                "satisfied": satisfied,
                "findings": sum(bool(item.findings) for item in report.verdicts),
            },
            "verdicts": [item.__dict__ for item in report.verdicts],
        }
    raise TypeError(f"unsupported report {type(report).__name__}")


def render(report: Any, output_format: str) -> str:
    """Render a report in one of the supported formats."""
    data = report_data(report)
    if output_format == "json":
        return json.dumps(data, indent=2, sort_keys=True) + "\n"
    if output_format == "markdown":
        if isinstance(report, VerdictReport):
            data = report_data(report)
            lines = [
                "| Requirement | Mapped | Tested | Satisfied | Findings |",
                "| --- | --- | --- | --- | --- |",
            ]
            lines.extend(
                f"| {item.requirement_id} | {'Yes' if item.mapped else 'No'} | "
                f"{'Yes' if item.tested else 'No'} | {'Yes' if item.satisfied else 'No'} | "
                f"{len(item.findings)} |"
                for item in report.verdicts
            )
            guidance = [item.guidance for item in report.verdicts if item.guidance]
            if guidance:
                lines.extend(["", *guidance])
            return "\n".join(lines) + "\n"
        return "\n".join(f"- **{key}**: {value}" for key, value in data.items()) + "\n"
    if output_format == "sarif":
        return (
            json.dumps(
                {
                    "version": "2.1.0",
                    "runs": [
                        {
                            "tool": {"driver": {"name": "niwoec"}},
                            "results": data.get("findings", []),
                        }
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    if isinstance(report, VerdictReport):
        summary = data["summary"]
        lines = [
            f"{summary['mapped']} mapped | {summary['tested']} tested | "
            f"{summary['satisfied']} satisfied | {summary['findings']} findings",
            "",
            "Requirement | Mapped | Tested | Satisfied | Findings",
            "------------|--------|---------|-----------|---------",
        ]
        lines.extend(
            f"{item.requirement_id} | {'Yes' if item.mapped else 'No'} | "
            f"{'Yes' if item.tested else 'No'} | {'Yes' if item.satisfied else 'No'} | "
            f"{len(item.findings)}"
            for item in report.verdicts
        )
        guidance = [item.guidance for item in report.verdicts if item.guidance]
        if guidance:
            lines.extend(["", *guidance])
        return "\n".join(lines) + "\n"
    return "\n".join(f"{key}: {value}" for key, value in data.items()) + "\n"
