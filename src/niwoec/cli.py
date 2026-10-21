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
    fuse,
    map_requirements,
    render,
    review,
    scan,
    verify,
)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return its public exit code."""
    parser = argparse.ArgumentParser(
        prog="niwoec", description="Offline deterministic FRS verifier"
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("scan", "review", "stubs"):
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
    command.add_argument("--format", choices=("text", "json", "sarif", "markdown"), default="text")
    sub.add_parser("help")
    try:
        args = parser.parse_args(argv)
        if args.command == "help":
            sys.stdout.write(parser.format_help())
            return 0
        report: Any
        if args.command in ("scan", "stubs"):
            report = scan(args.source)
        elif args.command == "review":
            report = review(args.source, Config())
        elif args.command == "map":
            report = map_requirements(args.spec, args.source)
        elif args.command == "verify":
            report = verify(args.spec, args.source)
        else:
            report = fuse(
                map_requirements(args.spec, args.source),
                scan(args.source),
                verify(args.spec, args.tests),
            )
        sys.stdout.write(render(report, args.format))
        if isinstance(report, ScanReport):
            return 1 if report.findings else 0
        return (
            1
            if args.command == "check" and any(not item.satisfied for item in report.verdicts)
            else 0
        )
    except (NiwoecError, OSError) as exc:
        sys.stderr.write(f"niwoec: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
