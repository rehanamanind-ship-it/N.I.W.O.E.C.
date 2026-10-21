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
