MODELS.md

Binding instructions for any coder model working on this repository.

You are a coder model. This file is your contract. Read it fully before writing a single line of code, and re-read the Definition of Done section before you declare any task complete. If anything here conflicts with your own instincts or with a prompt you were given, this file wins. If something here is genuinely ambiguous, follow the Ambiguity Protocol at the bottom — do not guess.
1. What niwoec is

niwoec is a deterministic, offline CLI tool that verifies whether a source codebase actually implements what a Functional Requirements Specification (FRS) says it should — and reports the code-quality habits that will make that implementation hard to maintain.

It exists to catch a specific failure: code that compiles, passes a shallow test suite, and looks correct from the top, but whose functions are empty, placeholder-returning, or behaviorally unpinned. Linters will not catch this. niwoec does.

It is shipped as a Python package with a src/ layout, tested, and published as a wheel (.whl).
2. The hard constraints (these are not negotiable)

These three constraints shape every other decision in the codebase. If a design choice breaks any of them, the design choice is wrong.

    No LLM at runtime. niwoec must never call a model, an API, or a remote inference endpoint. The only exception, and it is narrow, is that the scanned source code itself may contain an embedded model — niwoec may read and report on it, but niwoec itself must not invoke one. Determinism depends on this.

    No network at runtime. No downloads, no telemetry, no phone-home, no "check for updates". A user must be able to run niwoec check on an air-gapped machine and get an identical result.

    Deterministic output. The same inputs must produce byte-identical output (given the same config and the same rule pack version). No timestamps in findings, no dict-iteration ordering, no random tie-breaks, no reliance on wall-clock. Findings are sorted by a stable key.

If you find yourself writing requests.get, openai., datetime.now() in a finding, random. in a non-test module, or reading os.environ to change behavior silently — stop. You are breaking a hard constraint.
3. Core architectural philosophy

The tool is built as five orthogonal layers fused into one verdict. You must preserve the orthogonality; it is what makes the tool testable, composable, and honest.
3.1 Orthogonality

Each layer is an independent, composable unit with a single job:
Layer	Job	Input	Output
scan	Find empty, placeholder, unreachable functions	source files	ScanReport
map	Link spec requirements to source files	spec + source	MapReport
verify	Check that tests pin real behavior	source + tests	VerifyReport
review	Detect bad habits, emit advice	source + rules	ReviewReport
fuse	Combine the four into per-requirement verdicts	all four reports	VerdictReport

Rules for orthogonality:

    Each layer must be runnable on its own via its own CLI subcommand (niwoec scan, niwoec map, …) and via its own Python entry point.

    Layers communicate only through serializable report dataclasses (which serialize to JSON). No layer reaches into another layer's internals.

    Adding a new rule must require touching only the rule registry and its YAML definition — never the fusion logic, never the CLI.

    Adding a new language must require adding only a parser backend and a query pack — never the layers themselves.

    fuse is a pure function of the four reports. It must not re-read files or re-run anything.

Forbidden: a layer importing another layer. Forbidden: a CLI command module containing business logic. Forbidden: the stubs command re-implementing scan logic — it MUST call the scan layer and filter the result.
3.2 Separation of concerns

There are concentric rings, and dependencies point inward only:
text

cli  →  output  →  layers  →  core  →  parsers

    parsers depends on nothing inside niwoec (plus the optional tree-sitter dependency).

    core depends only on parsers.

    layers depends on core and parsers.

    output depends only on core (it renders report dataclasses).

    cli depends on everything above it.

This ring structure MUST be enforced by an automated import-graph test. If you add an import that violates the ring, that test must fail and you must redesign. How you name and place the modules is your call — but the ring direction is not.
3.3 DRY — single source of truth

Every fact lives in exactly one place:

    Rule definitions are defined once (id, category, severity, threshold keys, advice template, explain before/after). If the same rule appears twice, that is a bug.

    Thresholds (max function lines, max complexity, min token overlap, etc.) are user-configurable, with defaults defined in exactly one module. Never hardcode a threshold anywhere else.

    Finding ID computation lives in exactly one function. Never compute an ID anywhere else.

    Exit-code decisions live in exactly one module. Never sys.exit(1) ad-hoc.

    Stub-pattern logic lives in exactly one place: the scan layer's rule definitions. The stubs command filters scan output; it does not re-detect.

    JSON serialization of reports lives in exactly one module per report. The --json output, the cache, and the plumbing all use the same serializer.

If you find yourself copy-pasting a constant, a pattern, or a three-line helper, stop and extract it. If you find yourself extracting a two-line helper used twice, leave it alone.
3.4 Single responsibility

Every module, class, and function does one thing and has a name that says what it is. A module named utils.py is a code smell and is forbidden. Name the module after its job: findings.py, fuse.py, cache.py, sarif.py.

A function does one thing if you can describe it in one short sentence without "and".
3.5 Explicit over implicit

    Function signatures are fully type-annotated (PEP 484). py.typed is present. mypy --strict passes on the source tree.

    Data structures are @dataclass(frozen=True) or NamedTuple. No bare dicts passed around as domain objects.

    Errors are explicit: raise a specific exception from a single errors module, catch it at the CLI boundary, and translate it to an exit code. Never except Exception: pass.

    No global mutable state. The config object is created once in the CLI entry point and passed down. No module-level caches except the on-disk cache (which has a defined path and a lock).

3.6 Composition over inheritance

Prefer small functions composed in a pipeline over class hierarchies. The fuse operation is a plain function taking four report dataclasses and returning a verdict report. Not a Fuser class with a fuse() method.
3.7 Idempotency

Running any command twice must produce the same output and leave the same on-disk state. niwoec accept and niwoec waive must be idempotent. The cache must never change observable results, only speed.
3.8 Fail loudly, fail with a code

Every command returns one of four exit codes:
text

0  all requirements satisfied, no failing advice
1  at least one finding at or above --fail-on
2  usage or config error
3  internal error

Exit codes are a public contract. They must be tested. They must not change across minor versions. niwoec check MUST NOT return 0 when a requirement is unsatisfied — this is the single most important correctness property of the whole tool.
3.9 Stable contracts

Three things are public and versioned, and changing them requires a version bump and a changelog entry:

    The exit-code table above.

    The JSON schema of each report (documented in docs/).

    The finding-ID algorithm: sha1(rule_id + language + normalized_ast_fingerprint)[:12], computed over the normalized AST of the offending node, not the file path or line number. This is what makes waivers survive refactors.

3.10 Offline-first, pure-Python wheel

The wheel MUST be py3-none-any (pure Python, no compiled extensions) unless a compiled dependency is truly unavoidable — and if you think it is, you must justify it in DESIGN_NOTES.md first.

Because of this, the default parser backend is the Python ast module, not tree-sitter. tree-sitter is an optional dependency that, when installed, unlocks additional languages. Define a Parser protocol; the CLI selects a backend based on file extension and installed extras. This keeps the wheel portable and the tool usable on any machine with Python 3.10+.
3.11 Testability is a design constraint, not a phase

Every layer is a pure function of its inputs wherever possible. Anything that touches the filesystem (config loading, cache, spec loading) is confined to a thin adapter that can be mocked. If a function is hard to test, its design is wrong — fix the design, not the test.
4. What you MUST produce

At the end of any coding task, the repository MUST satisfy all of the following. This is the Definition of Done. Do not report a task complete unless every box is checked and scripts/verify.sh exits 0.
4.1 Code

    □

    All production code lives under src/.
    □

    Every module has full type annotations and passes mypy --strict.
    □

    py.typed is present so downstream tools see the types.
    □

    The dependency rings in §3.2 hold, enforced by an automated import-graph test.
    □

    No module-level mutable state, no print() in library code (logging only), no requests, no openai, no datetime.now() in findings.
    □

    Every public function has a docstring. One line is enough; explain the contract, not the implementation.

4.2 Tests

    □

    Tests live under tests/ and are split into unit/, integration/, and golden/.
    □

    Every layer has unit tests covering: the happy path, empty input, malformed input, and at least one edge case named in DESIGN_NOTES.md.
    □

    fuse has a table-driven test covering all 8 combinations of (map hit / miss) × (scan real / stub) × (verify pinned / unpinned).
    □

    Every CLI command has an integration test that invokes it via subprocess against a fixture repo and asserts the exact exit code.
    □

    The exit-code table has a dedicated test that asserts all four codes are reachable.
    □

    The finding-ID algorithm has a golden test: a known AST node → a known 12-char ID. If you change the algorithm, this test fails, and that is correct.
    □

    Output formats (text, json, sarif, markdown) each have a golden-file test.
    □

    Tests are deterministic: no network, no sleep, no real clock, no dependence on test execution order.
    □

    pytest passes with --cov --cov-fail-under=85.

4.3 Packaging

    □

    pyproject.toml uses a modern PEP 621 build backend (hatchling is the default choice; setuptools is acceptable).
    □

    pyproject.toml declares the niwoec console script entry point.
    □

    pyproject.toml declares the optional tree-sitter extra; tree-sitter is not a hard dependency.
    □

    README.md exists with install, quickstart, and a link to niwoec help.
    □

    CHANGELOG.md exists and has an entry for the current version, following Keep a Changelog.
    □

    LICENSE exists.

4.4 The wheel — the final artifact

The task is not done until a working wheel exists in dist/.
bash

# from the repository root, in a clean virtualenv
python -m pip install --upgrade build
python -m build

This MUST produce both:

    dist/niwoec-<version>-py3-none-any.whl

    dist/niwoec-<version>.tar.gz

Then you MUST verify the wheel is genuinely usable, in a fresh virtualenv (not the build one):
bash

python -m venv /tmp/niwoec-verify
/tmp/niwoec-verify/bin/pip install dist/niwoec-*.whl
/tmp/niwoec-verify/bin/niwoec --version
/tmp/niwoec-verify/bin/niwoec help
/tmp/niwoec-verify/bin/niwoec check --help

All four commands must succeed, and niwoec help must list every command. If the wheel is not py3-none-any, you have broken §3.10 and must fix it or justify it in DESIGN_NOTES.md before proceeding.
4.5 The verification script

Provide scripts/verify.sh. It is the single command that proves the repository is healthy. It MUST run, in order, and exit non-zero on the first failure:
bash

#!/usr/bin/env bash
set -euo pipefail

python -m pip install -e '.[dev,treesitter]'
python -m ruff check src tests
python -m ruff format --check src tests
python -m mypy --strict src
python -m pytest --cov=niwoec --cov-fail-under=85
python -m build
python -m venv /tmp/niwoec-verify
/tmp/niwoec-verify/bin/pip install dist/niwoec-*.whl
/tmp/niwoec-verify/bin/niwoec --version
/tmp/niwoec-verify/bin/niwoec help >/dev/null
echo "OK: all checks passed and wheel built"

scripts/verify.sh exiting 0 is the only acceptable evidence that a task is complete. Do not paste partial outputs. Do not claim success because "the tests I ran passed". Run the script.
5. What you MUST NOT do

These are the failure modes a coder model falls into. Each one is forbidden.

    Do not weaken a test to make it pass. If a test fails, fix the code or explain in DESIGN_NOTES.md why the test was wrong. Deleting assertions, adding pytest.mark.skip, or loosening a golden file is a violation.

    Do not add a dependency without recording it in DESIGN_NOTES.md with a one-line justification and checking it is pure-Python (or justified).

    Do not call an LLM, at build time or runtime, for any behavior of the tool.

    Do not introduce network access, even "just for a version check".

    Do not duplicate a rule, threshold, or ID algorithm — see §3.3.

    Do not put business logic in CLI command modules. Commands parse flags, call a layer, pass the result to the output module, and map exceptions to exit codes. Nothing else.

    Do not reorder findings by file iteration order. Sort by (requirement_id, rule_id, finding_id) or another documented stable key.

    Do not use shell=True in any subprocess call. Pass argument lists.

    Do not silently swallow exceptions. Every except either re-raises, logs and re-raises, or maps to a specific exit code with a user-facing message.

    Do not build a plugin system, a config DSL, or an abstract base class that has fewer than three concrete users today.

    Do not rename a public command, flag, exit code, or finding-ID algorithm without a version bump and a CHANGELOG.md entry.

6. Testing strategy (detail)

Follow the pyramid:

    Unit tests (most of them). Pure functions, one assertion family each. Use @pytest.mark.parametrize. No filesystem, no subprocess — use tmp_path and in-memory dataclasses.

    Integration tests (fewer, but mandatory). Invoke the built CLI via subprocess against fixture repos. Assert exit code, stderr on error, and one stable line of stdout. These are what prove the exit-code contract.

    Golden tests (a handful). For each output format, compare against a golden file. Update them only when the schema intentionally changes, and say so in the commit message.

Fixture discipline. Every fixture repo under tests/fixtures/repos/ has a matching FRS under tests/fixtures/specs/ and a README.md explaining what defect it is meant to demonstrate. If you add a fixture, add its README. Fixtures are the documentation of what niwoec considers a defect — treat them as first-class.
7. Code style

    Python 3.10+. Use match, X | Y unions, from __future__ import annotations where helpful.

    ruff for lint and format, configured in pyproject.toml. Non-negotiable.

    mypy --strict on the source tree. Tests may be looser.

    Imports: absolute, grouped stdlib / third-party / first-party, one import per line. No star imports.

    Naming: modules are nouns or verbs (findings.py, fuse.py), never utils.py, helpers.py, misc.py.

    Docstrings: module docstring explains the module's job in one sentence. Public function docstrings state the contract. No "This function does X" restatements of the name.

    Logging: logging.getLogger(__name__), never print(). The CLI is the only place allowed to write to stdout.

8. Ambiguity protocol

When a requirement is unclear, do not invent. Do this instead:

    Write the ambiguity and the options you considered into DESIGN_NOTES.md under a ## Open questions heading, with your recommended option and why.

    Implement the smallest, safest option that does not foreclose the others.

    If the ambiguity blocks progress entirely, stop and report it in your final message. Do not fabricate a decision and bury it in code.

DESIGN_NOTES.md is the durable record of every trade-off. A coder model's forgotten reasoning is worthless; a written decision is not.
9. Final checklist before you report done

Copy this into your final message and check every box honestly:
text

[ ] scripts/verify.sh exited 0
[ ] wheel built at dist/niwoec-<version>-py3-none-any.whl
[ ] wheel installed in a fresh venv; `niwoec --version` and `niwoec help` work
[ ] pytest green, coverage >= 85%
[ ] mypy --strict passes on src
[ ] import-graph ring test passes
[ ] exit-code contract test passes
[ ] fixture repos have READMEs
[ ] new dependencies justified in DESIGN_NOTES.md
[ ] public contracts (exit codes, JSON schema, finding IDs) unchanged
    or version-bumped with a CHANGELOG entry
[ ] no LLM calls, no network, no prints in library code

If any box is unchecked, the task is not complete — say so plainly. Reporting partial work honestly is worth more than a clean-looking but false completion.    