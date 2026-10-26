# niwoec

niwoec is a deterministic, offline command-line tool for checking whether a
source codebase implements the requirements in a Functional Requirements
Specification (FRS). It also reports placeholder functions and simple
maintainability issues that can make an implementation difficult to trust.

niwoec is designed for local and air-gapped use:

- It does not call an LLM or a remote inference service.
- It does not download files, send telemetry, or check for updates.
- The same source, FRS, configuration, and rule version produce stable output.
- The default Python parser uses the standard library `ast` module.

## Installation

### Install from a wheel

```bash
python -m pip install dist/niwoec-3.0.0-py3-none-any.whl
```

### Install from the source tree

```bash
python -m pip install .
```

For development, install the test and quality tools as well:

```bash
python -m pip install -e '.[dev,treesitter]'
```

The optional `treesitter` extra is not required by the default Python
implementation.

## Quickstart

Given a source directory and an FRS file:

```bash
niwoec check requirements.frs src/ --tests tests/
```

To opt into bounded local dynamic testing:

```bash
niwoec check requirements.frs src/ --tests tests/ --dynamic
```

Dynamic mode runs the local pytest suite in a subprocess, collects at most
1,000 tests, and enforces a 30-second collection and execution timeout. It
captures test failures but does not and cannot try every possible input. It
does not contact the network on niwoec's behalf, but the executed project code
may perform its own side effects. niwoec asks for two separate confirmations
before execution. Use it only with trusted local code.

For stronger bounded evidence about whether tests are meaningful, use mutation
analysis:

```bash
niwoec check requirements.frs src/ --tests tests/ --deep
```

Deep mode first runs the baseline tests, then mutates up to 50 common arithmetic,
comparison, and literal expressions in temporary copies of the project. A
mutant is **killed** when tests fail, and **survived** when tests still pass.
Surviving mutants identify behavior that the tests did not detect. This is
evidence, not a proof of correctness or exhaustive input coverage.

Inspect one layer at a time:

```bash
niwoec scan src/
niwoec map requirements.frs src/
niwoec verify requirements.frs tests/
niwoec review src/
niwoec online src/
```

Use JSON when another tool needs to consume the result:

```bash
niwoec check requirements.frs src/ --tests tests/ --format json
```

For CI-friendly Markdown output:

```bash
niwoec check requirements.frs src/ --tests tests/ --format markdown
```

The available commands and options are also listed by:

```bash
niwoec help
niwoec --help
niwoec check --help
```

## FRS format

The current FRS adapter accepts one requirement per line using:

```text
requirement_id: requirement description
```

Requirement identifiers may contain letters, numbers, underscores, dots, and
hyphens. Blank lines and lines without a colon are ignored.

Example:

```text
add: add two numbers and return the result.
save_message: prepare a message for storage.
```

The mapper first looks for the requirement identifier in source files. This
keeps similarly worded requirements from being linked to unrelated files.

## Example project

The distribution includes a ready-to-run example in [`examples/`](./examples/):

- [`app.py`](./examples/app.py) contains two implemented functions.
- [`stubs.py`](./examples/stubs.py) contains an intentional placeholder.
- [`requirements.frs`](./examples/requirements.frs) contains the FRS.
- [`test_app.py`](./examples/test_app.py) references tested requirements.
- [`README.md`](./examples/README.md) gives the example-specific instructions.

Run it from the repository root:

```bash
niwoec scan examples
niwoec map examples/requirements.frs examples
niwoec verify examples/requirements.frs examples/test_app.py
niwoec check examples/requirements.frs examples --tests examples/test_app.py
```

The final command intentionally returns exit code `1`: `add` and
`save_message` are satisfied, while `pending_feature` is a placeholder without
a behavioral test.

## Commands

| Command | Purpose |
| --- | --- |
| `scan SOURCE` | Find empty and placeholder Python functions. |
| `map SPEC SOURCE` | Link FRS requirements to source files. |
| `verify SPEC TESTS` | Find requirements referenced by tests. |
| `review SOURCE` | Report functions over the configured line threshold. |
| `online SOURCE` | Detect URLs and network/API calls without making network requests. |
| `check SPEC SOURCE` | Combine mapping, scanning, and verification into verdicts. |
| `stubs SOURCE` | Run the scan layer for placeholder findings. |

`SOURCE` and `TESTS` may be a Python file or a directory. Directory traversal
is deterministic and considers Python files in sorted order.

The `online` command is intentionally offline. It identifies external URLs and
common HTTP/API calls so they can be covered by an integration test or an
offline endpoint contract. It never probes an endpoint, downloads data, or
changes the result based on internet availability.

`check` reports mapping and test coverage independently. A requirement can be
mapped but untested. This is **UNVERIFIED**, not a code failure: niwoec has not
enough evidence to issue a final satisfied/failed verdict. It produces guidance
such as:

```text
💡 Missing behavioral test reference: load_model; Suggested test name: test_load_model_...

Human-readable output uses:

- ✅ `SATISFIED` — mapped, tested, and no implementation findings.
- 🟡 `UNVERIFIED` — missing source mapping or behavioral-test evidence; this is
  not automatically a code error.
- ❌ `FAILED` — implementation findings were detected.
```

Use `--untested info`, `--untested warning`, or `--untested failure` to label
untested requirements for a project's policy. Use `--min-coverage 100` with a
Cobertura XML report (default `coverage.xml`) to enforce a coverage threshold:

```bash
niwoec check requirements.frs src --tests tests \
  --min-coverage 100 --coverage-file coverage.xml
```

The report is read locally by niwoec; it never runs tests or accesses the
network.

## GitHub Actions

The command is suitable for an offline or controlled CI job:

```yaml
- run: python -m pip install -e '.[dev]'
- run: niwoec check requirements.frs src --tests tests --format sarif > niwoec.sarif
- uses: actions/upload-artifact@v4
  with:
    name: niwoec-report
    path: niwoec.sarif
```

## Output formats

Every analysis command accepts `--format`:

- `text` — compact human-readable output (the default).
- `json` — stable, indented JSON suitable for automation.
- `markdown` — simple Markdown summaries.
- `sarif` — SARIF-shaped JSON for findings integration.

## Exit codes

| Code | Meaning |
| ---: | --- |
| `0` | All checked requirements are satisfied and no failing finding is present. |
| `1` | At least one requirement is unsatisfied or a finding was reported. |
| `2` | Usage, input, or configuration error. |
| `3` | Reserved for internal errors. |

## Development and verification

The repository's single verification command is:

```bash
./scripts/verify.sh
```

It runs linting, formatting checks, strict type checking, the test suite with
coverage, wheel building, and installation of the wheel into a fresh virtual
environment.

## License

niwoec is distributed under the MIT License. See [`LICENSE`](./LICENSE).
