#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"

.venv/bin/ruff check src tests
.venv/bin/mypy
.venv/bin/pytest -q
.venv/bin/python -m build --wheel --outdir /tmp/chaos-agent-release-build
git diff --check

if find . -path './.git' -prune -o -path './.venv' -prune -o -path './.mypy_cache' -prune -o -path './.pytest_cache' -prune -o -type f \( -name '*.db' -o -name '*.pem' -o -name 'id_*' \) -not -path './secrets/ssh/.gitkeep' -print | grep -q .; then
    echo "release check: operational credential or runtime artifact found" >&2
    exit 1
fi

echo "Release checks passed; real-target and Docker checks require their explicit environments."
