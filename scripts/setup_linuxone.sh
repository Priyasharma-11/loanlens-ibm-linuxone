#!/usr/bin/env bash
# Run on the LinuxONE VM inside the project directory. Creates venv, installs core deps, trains, tests.
set -euo pipefail
echo "arch: $(uname -m)  python: $(python3 --version)"
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-core.txt            # if this fails, see docs/DEPLOY_LINUXONE.md (distro packages)
python -m loanlens.train --dataset "${LOANLENS_DATASET:-auto}"
python scripts/find_demo_profile.py || true
python -m unittest discover -s tests -t . -q
python scripts/linuxone_evidence.py > /dev/null && echo "evidence written to evidence/linuxone_evidence.json"
echo "Setup OK. Start API:  LOANLENS_REVIEWER_TOKEN=change-me ./scripts/run_api.sh"
