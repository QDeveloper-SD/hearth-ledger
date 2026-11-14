#!/usr/bin/env bash
# Build the desktop package: vite build -> PyInstaller backend -> electron-builder.
# Builds for the host OS (PyInstaller cannot cross-compile). Output: release/
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements-build.txt
if command -v bun >/dev/null 2>&1; then bun install && bun run build; else { [ -d node_modules ] || npm install --no-audit --no-fund; } && npm run build; fi
[ -x node_modules/electron/dist/electron ] || node node_modules/electron/install.js
rm -rf build/pyinstaller build/pyi-work
.venv/bin/pyinstaller --noconfirm --distpath build/pyinstaller --workpath build/pyi-work hearth-backend.spec
npx electron-builder --publish never ${HEARTH_BUILDER_ARGS:-}
echo "Done. See release/"
