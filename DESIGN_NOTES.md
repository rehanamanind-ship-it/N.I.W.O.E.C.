# Design notes

## Decisions

- The initial FRS adapter accepts deterministic `id: description` lines. This is
  intentionally small and leaves room for a documented schema extension.
- Python's standard-library `ast` is the default parser, keeping the wheel pure
  Python and offline. The tree-sitter extra is optional and currently reserved
  for future parser backends.

## Open questions

- The FRS format may eventually need structured YAML. The smallest safe current
  option is the line format above because it requires no dependency or network.
