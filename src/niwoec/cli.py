"""The niwoec command-line interface."""

import argparse
import sys
from pathlib import Path
from typing import Any

from niwoec import __version__
from niwoec.core import (
    Config,
    NiwoecError,
    ScanReport,
    enforce_coverage,
    dynamic_test,
    deep_test,
    upgrade_local,
    fuse,
    map_requirements,
    render,
    review,
    online,
    scan,
    verify,
)


def _confirm_dynamic_execution() -> None:
    """Require two explicit confirmations before running project tests."""
    prompts = (
        "Dynamic mode will execute project test code. This may perform file, "
        "process, or network operations. Continue? [y/N] ",
        "Final confirmation: execute the selected tests now? [y/N] ",
    )
    for prompt in prompts:
        try:
            answer = input(prompt)
        except EOFError as exc:
            raise NiwoecError("dynamic execution requires two confirmations") from exc
        if answer.strip().lower() not in {"y", "yes"}:
            raise NiwoecError("dynamic execution cancelled")


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return its public exit code."""
    parser = argparse.ArgumentParser(
        prog="niwoec", description="Offline deterministic FRS verifier"
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("scan", "review", "online", "stubs"):
        command = sub.add_parser(name)
        command.add_argument("source", type=Path)
        command.add_argument(
            "--format", choices=("text", "json", "sarif", "markdown"), default="text"
        )
    for name in ("map", "verify"):
        command = sub.add_parser(name)
        command.add_argument("spec", type=Path)
        command.add_argument("source", type=Path)
        command.add_argument(
            "--format", choices=("text", "json", "sarif", "markdown"), default="text"
        )
    command = sub.add_parser("check")
    command.add_argument("spec", type=Path)
    command.add_argument("source", type=Path)
    command.add_argument("--tests", type=Path, default=Path("tests"))
    command.add_argument(
        "--untested",
        choices=("info", "warning", "failure"),
        default="warning",
        help="severity assigned to requirements without behavioral tests",
    )
    command.add_argument("--min-coverage", type=float, default=None)
    command.add_argument("--coverage-file", type=Path, default=Path("coverage.xml"))
    command.add_argument(
        "--dynamic",
        action="store_true",
        help="opt in to bounded local pytest execution",
    )
    command.add_argument(
        "--deep",
        action="store_true",
        help="run bounded tests and deterministic mutation analysis",
    )
    command.add_argument("--dynamic-project", type=Path, default=Path("."))
    command.add_argument("--format", choices=("text", "json", "sarif", "markdown"), default="text")
    sub.add_parser("help")
    upgrade = sub.add_parser("upgrade")
    upgrade.add_argument("artifact", type=Path)
    upgrade.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    try:
        args = parser.parse_args(argv)
        if args.command == "help":
            sys.stdout.write(parser.format_help())
            return 0
        if args.command == "upgrade":
            _confirm_dynamic_execution()
            upgrade_report = upgrade_local(args.artifact)
            sys.stdout.write(render(upgrade_report, args.format))
            return 0 if upgrade_report.status == "installed" else 1
        report: Any
        if args.command in ("scan", "stubs"):
            report = scan(args.source)
        elif args.command == "review":
            report = review(args.source, Config())
        elif args.command == "online":
            report = online(args.source)
        elif args.command == "map":
            report = map_requirements(args.spec, args.source)
        elif args.command == "verify":
            report = verify(args.spec, args.source)
        else:
            if args.min_coverage is not None and not 0 <= args.min_coverage <= 100:
                raise NiwoecError("--min-coverage must be between 0 and 100")
            if args.min_coverage is not None:
                enforce_coverage(args.min_coverage, args.coverage_file)
            report = fuse(
                map_requirements(args.spec, args.source),
                scan(args.source),
                verify(args.spec, args.tests),
                Config(untested_severity=args.untested),
            )
            if args.dynamic or args.deep:
                _confirm_dynamic_execution()
                if args.deep:
                    deep = deep_test(args.source, args.tests, args.dynamic_project)
                    sys.stdout.write(render(deep, args.format))
                    if deep.baseline.status != "passed" or deep.survived or deep.timed_out:
                        return 1
                else:
                    dynamic = dynamic_test(args.tests, args.dynamic_project)
                    sys.stdout.write(render(dynamic, args.format))
                if args.dynamic and dynamic.status != "passed":
                    return 1
        sys.stdout.write(render(report, args.format))
        if isinstance(report, ScanReport):
            return 1 if report.findings else 0
        return (
            1
            if args.command == "check"
            and any(
                item.status == "failed"
                or item.status == "unverified"
                and item.severity == "failure"
                for item in report.verdicts
            )
            else 0
        )
    except (NiwoecError, OSError) as exc:
        sys.stderr.write(f"niwoec: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
