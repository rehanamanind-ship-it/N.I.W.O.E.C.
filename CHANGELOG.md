# Changelog

All notable changes are documented here.

## [3.0.0] - 2026-10-26

Version 3.0.0 is a major analysis and reporting release. It moves niwoec from
primarily static requirement inspection toward layered evidence gathering while
preserving deterministic, offline-first defaults.

### Dynamic and deep analysis

- Added opt-in bounded pytest execution through a subprocess.
- Added a 30-second collection and execution timeout.
- Added a 1,000-test collection limit.
- Added captured test output and explicit passed, failed, and timeout results.
- Added two separate confirmations before project code is executed.
- Added deterministic mutation analysis in a temporary project copy.
- Added arithmetic, comparison, boolean, numeric, and string mutation samples.
- Added killed, survived, and timed-out mutant reporting so weak behavioral
  tests produce concrete evidence instead of only a test-presence signal.

### Requirement evidence

- Separated `mapped`, `tested`, and `satisfied` states.
- Added `SATISFIED`, `UNVERIFIED`, and `FAILED` verdict statuses.
- Missing test references are reported as `UNVERIFIED`, not as code failures.
- Added suggested behavioral test names for unverified requirements.
- Added test-reference discovery from function names, docstrings, decorators,
  explicit markers, and comments.
- Added configurable untested severity with `--untested info|warning|failure`.
- Added Cobertura XML enforcement with `--min-coverage` and `--coverage-file`.

### Reporting and integrations

- Replaced opaque default dictionary output with deterministic summary tables.
- Added emoji status indicators and line-by-line requirement results.
- Preserved stable JSON, Markdown, and SARIF output for automation and CI.
- Added offline URL and common API-call detection through the `online` command.
- Added GitHub Actions documentation for publishing SARIF artifacts.

### Compatibility and safety

- Static commands remain offline, deterministic, and non-executing.
- Dynamic execution is explicit and requires two confirmations.
- Added a confirmation-protected offline `upgrade` command for local wheels and
  source archives; it never contacts GitHub or package indexes.
- Existing Click-style command-group false-positive handling is preserved.
- The wheel remains pure Python and includes the example project.

## [2.2.0] - 2026-10-25

- Separated mapped, tested, and satisfied requirement states.
- Added deterministic summary-table output and missing-test guidance.
- Added test-reference discovery from names, docstrings, decorators, and markers.
- Added configurable untested severity and `--min-coverage` validation.
- Added GitHub Actions SARIF artifact documentation.

## [2.1.0] - 2026-10-24

- Added offline detection for external URLs and common network/API calls.
- Added the `online` command for reviewing online dependencies without making
  network requests.
- Ignore Click-style command-group registration callbacks when they own child
  commands, while continuing to report ordinary placeholder functions.


## [1.0.0] - 2026-10-21

- Initial stable release with offline scanner, mapper, verifier, reviewer, fusion
  report, and CLI.
