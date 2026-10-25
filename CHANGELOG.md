# Changelog

All notable changes are documented here.

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
