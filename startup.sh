#!/usr/bin/env bash
# Starts the hub on this PC. Run `python -m agent` manually on any other
# registered PC instead (see README.md).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f .env ]; then
    echo "Missing .env — copy .env.template to .env and fill it in first." >&2
    exit 1
fi

exec python -m hub
