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
python -m pip install dist/niwoec-1.0.0-py3-none-any.whl
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

Inspect one layer at a time:

```bash
niwoec scan src/
niwoec map requirements.frs src/
niwoec verify requirements.frs tests/
niwoec review src/
```

Use JSON when another tool needs to consume the result:

```bash
niwoec check requirements.frs src/ --tests tests/ --format json
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
| `check SPEC SOURCE` | Combine mapping, scanning, and verification into verdicts. |
| `stubs SOURCE` | Run the scan layer for placeholder findings. |

`SOURCE` and `TESTS` may be a Python file or a directory. Directory traversal
is deterministic and considers Python files in sorted order.

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
