# Changelog

All notable changes are documented here.

## [2.1.0] - 2026-10-24

- Added offline detection for external URLs and common network/API calls.
- Added the `online` command for reviewing online dependencies without making
  network requests.

## [Unreleased]

- Ignore Click-style command-group registration callbacks when they own child
  commands, while continuing to report ordinary placeholder functions.
- Detect external URLs and common network/API calls without making runtime
  network requests.

## [1.0.0] - 2026-10-21

- Initial stable release with offline scanner, mapper, verifier, reviewer, fusion
  report, and CLI.
