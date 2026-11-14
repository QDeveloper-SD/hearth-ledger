#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
if [ ! -d dist ]; then
  if command -v bun >/dev/null 2>&1; then bun install && bun run build; else { [ -d node_modules ] || npm install --no-audit --no-fund; } && npm run build; fi
fi
exec python -m backend
