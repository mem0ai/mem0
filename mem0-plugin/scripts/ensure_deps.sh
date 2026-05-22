#!/usr/bin/env bash
# Install mem0ai SDK into a persistent venv inside CLAUDE_PLUGIN_DATA.
# Runs on SessionStart; skips if requirements.txt hasn't changed.
set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA_DIR="${CLAUDE_PLUGIN_DATA:-${HOME}/.mem0/plugin-data}"
VENV_DIR="${DATA_DIR}/venv"
REQ_SRC="${PLUGIN_ROOT}/requirements.txt"
REQ_STAMP="${DATA_DIR}/requirements.txt"

mkdir -p "${DATA_DIR}"

needs_install=false

if [ ! -f "${VENV_DIR}/bin/python3" ]; then
  needs_install=true
elif ! diff -q "${REQ_SRC}" "${REQ_STAMP}" >/dev/null 2>&1; then
  needs_install=true
fi

if [ "${needs_install}" = "true" ]; then
  python3 -m venv "${VENV_DIR}" 2>/dev/null || python -m venv "${VENV_DIR}"
  "${VENV_DIR}/bin/pip" install --quiet --upgrade pip >/dev/null 2>&1 || true
  if "${VENV_DIR}/bin/pip" install --quiet -r "${REQ_SRC}" 2>/dev/null; then
    cp "${REQ_SRC}" "${REQ_STAMP}"
  else
    rm -f "${REQ_STAMP}"
    echo "mem0 plugin: failed to install Python dependencies" >&2
    exit 0
  fi
fi
