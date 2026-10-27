# niwoec examples

These files demonstrate the expected input format:

- [`src/app.py`](./src/app.py) contains two implemented functions.
- [`src/stubs.py`](./src/stubs.py) contains one placeholder function.
- [`requirements.frs`](./requirements.frs) contains one `id: description`
  requirement per line.
- [`tests/test_app.py`](./tests/test_app.py) references the requirements that
  have behavioral tests.

From the repository root, try:

```bash
niwoec scan examples
niwoec map examples/requirements.frs examples
niwoec verify examples/requirements.frs examples/tests
niwoec check examples/requirements.frs examples --tests examples/tests
```

The `check` command should return exit code `1` because `pending_feature` is a
placeholder and has no test.
