#!/usr/bin/env bash
# In-process UI:            ./scripts/run_ui.sh
# UI -> remote LinuxONE API: LOANLENS_API_URL=http://localhost:8000 ./scripts/run_ui.sh   (after an SSH tunnel)
cd "$(dirname "$0")/.."; [ -d .venv ] && source .venv/bin/activate
exec streamlit run app/streamlit_app.py --server.address "${UI_HOST:-127.0.0.1}" --server.port "${UI_PORT:-8501}"
