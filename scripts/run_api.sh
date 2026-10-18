#!/usr/bin/env bash
# Usage: LOANLENS_REVIEWER_TOKEN=change-me ./scripts/run_api.sh [host] [port]   (default 127.0.0.1:8000)
cd "$(dirname "$0")/.."; [ -d .venv ] && source .venv/bin/activate
exec python -m loanlens.server --host "${1:-127.0.0.1}" --port "${2:-8000}"
