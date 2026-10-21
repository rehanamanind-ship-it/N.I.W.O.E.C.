"""Small typed contracts and analysis functions for niwoec."""

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class NiwoecError(Exception):
    """Base class for expected user-facing errors."""


class InputError(NiwoecError):
    """Invalid or unreadable input."""


@dataclass(frozen=True)
class Config:
    """Runtime thresholds."""

    max_function_lines: int = 40


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
    satisfied: bool
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


def _stub(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
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
    return len(body) == 1 and isinstance(body[0], ast.Return) and body[0].value is None


def scan(path: Path) -> ScanReport:
    """Find empty and placeholder functions."""
    findings: list[Finding] = []
    for file in _files(path):
        for node in ast.walk(parse(file)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _stub(node):
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
    return MapReport(tuple(sorted(set(links))))


def verify(spec: Path, tests: Path) -> VerifyReport:
    """Mark requirements referenced in test files."""
    try:
        requirements = [
            line.split(":", 1)[0].strip()
            for line in spec.read_text(encoding="utf-8").splitlines()
            if ":" in line
        ]
        content = "\n".join(file.read_text(encoding="utf-8") for file in _files(tests))
    except (OSError, UnicodeError) as exc:
        raise InputError(f"cannot read verification input: {exc}") from exc
    return VerifyReport(tuple(item for item in requirements if item in content))


def review(path: Path, config: Config) -> ReviewReport:
    """Find functions exceeding the configured line limit."""
    findings: list[Finding] = []
    for file in _files(path):
        for node in ast.walk(parse(file)):
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
    return ReviewReport(
        tuple(sorted(findings, key=lambda item: (item.file, item.line, item.finding_id)))
    )


def fuse(mapped: MapReport, scanned: ScanReport, verified: VerifyReport) -> VerdictReport:
    """Combine reports without reading files."""
    requirements = sorted({item for item, _ in mapped.links} | set(verified.pinned))
    verdicts = []
    for requirement in requirements:
        files = {file for item, file in mapped.links if item == requirement}
        findings = tuple(item.finding_id for item in scanned.findings if item.file in files)
        verdicts.append(
            Verdict(
                requirement,
                bool(files and requirement in verified.pinned and not findings),
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
        return {"verdicts": [item.__dict__ for item in report.verdicts]}
    raise TypeError(f"unsupported report {type(report).__name__}")


def render(report: Any, output_format: str) -> str:
    """Render a report in one of the supported formats."""
    data = report_data(report)
    if output_format == "json":
        return json.dumps(data, indent=2, sort_keys=True) + "\n"
    if output_format == "markdown":
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
    return "\n".join(f"{key}: {value}" for key, value in data.items()) + "\n"
