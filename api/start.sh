#!/bin/sh
# Use a file rather than nested shell quoting in hosting command overrides.
# Stop on a failed migration; never serve the API against an incompatible schema.
set -eu
cd "$(dirname "$0")"
python -m alembic upgrade head
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
