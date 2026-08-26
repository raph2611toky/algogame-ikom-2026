#!/usr/bin/env bash
set -euo pipefail
exec uvicorn app.main:app --host "${KAKAFANDODO_HOST:-127.0.0.1}" --port "${KAKAFANDODO_PORT:-8000}"

