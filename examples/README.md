# niwoec examples

These files demonstrate the expected input format:

- [`app.py`](./app.py) contains two implemented functions.
- [`stubs.py`](./stubs.py) contains one placeholder function.
- [`requirements.frs`](./requirements.frs) contains one `id: description`
  requirement per line.
- [`test_app.py`](./test_app.py) references the requirements that have behavioral
  tests.

From the repository root, try:

```bash
niwoec scan examples
niwoec map examples/requirements.frs examples
niwoec verify examples/requirements.frs examples/test_app.py
niwoec check examples/requirements.frs examples --tests examples/test_app.py
```

The `check` command should return exit code `1` because `pending_feature` is a
placeholder and has no test.
