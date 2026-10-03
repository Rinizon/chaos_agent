#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"

acceptance_dir=$(mktemp -d "${TMPDIR:-/tmp}/chaos-agent-acceptance.XXXXXX")
trap 'rm -rf "$acceptance_dir"' EXIT INT TERM

uv run ruff check .
uv run ruff format --check .
uv run mypy src/chaos_agent
uv run pytest -q
uv run python -m build --sdist --wheel --outdir "$acceptance_dir/build"

CHAOS_DATABASE_URL="sqlite:///$acceptance_dir/migration.db" uv run alembic upgrade head
CHAOS_DATABASE_URL="sqlite:///$acceptance_dir/migration.db" uv run alembic current | grep -Fq '0004 (head)'

uv run python -m py_compile ops/target/target-helper ops/target/ssh-dispatcher
git diff --check

if find . -path './.git' -prune -o -path './.venv' -prune -o -path './.mypy_cache' -prune -o -path './.pytest_cache' -prune -o -type f \( -name '*.db' -o -name '*.pem' -o -name 'id_*' \) -not -path './secrets/ssh/.gitkeep' -print | grep -q .; then
    echo "release check: operational credential or runtime artifact found" >&2
    exit 1
fi

echo "Local acceptance checks passed; Docker and real-target checks require operator approval."
