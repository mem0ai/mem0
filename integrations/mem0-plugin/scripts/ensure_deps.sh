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

LOCKDIR="${DATA_DIR}/.install-lock"

# A venv puts its interpreter in bin/ on POSIX and Scripts/ on Windows.
# Echoes the venv interpreter path, or nothing if the venv is absent/incomplete.
venv_python() {
  for _candidate in \
    "${VENV_DIR}/bin/python3" \
    "${VENV_DIR}/bin/python" \
    "${VENV_DIR}/Scripts/python.exe"
  do
    if [ -x "${_candidate}" ]; then
      echo "${_candidate}"
      return 0
    fi
  done
  return 1
}

needs_install=false

if ! venv_python >/dev/null; then
  needs_install=true
elif ! diff -q "${REQ_SRC}" "${REQ_STAMP}" >/dev/null 2>&1; then
  needs_install=true
fi

if [ "${needs_install}" = "true" ]; then
  if mkdir "${LOCKDIR}" 2>/dev/null; then
    # We acquired the lock — proceed with installation
    trap 'rmdir "${LOCKDIR}" 2>/dev/null || true' EXIT
    python3 -m venv "${VENV_DIR}" 2>/dev/null || python -m venv "${VENV_DIR}"
    # Resolve after creation, and go through `-m pip` so only one path needs resolving.
    VENV_PY="$(venv_python || true)"
    if [ -n "${VENV_PY}" ]; then
      "${VENV_PY}" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
    fi
    if [ -n "${VENV_PY}" ] && "${VENV_PY}" -m pip install --quiet -r "${REQ_SRC}" 2>/dev/null; then
      cp "${REQ_SRC}" "${REQ_STAMP}"
      rm -f "${DATA_DIR}/.install-failed"
    else
      rm -f "${REQ_STAMP}"
      touch "${DATA_DIR}/.install-failed"
      echo "mem0 plugin: failed to install Python dependencies" >&2
      exit 0
    fi
  else
    # Another process holds the lock — wait up to 60s for it to finish
    for i in $(seq 1 60); do
      [ ! -d "${LOCKDIR}" ] && break
      sleep 1
    done
    # Check if the other process's install failed
    if [ -f "${DATA_DIR}/.install-failed" ]; then
      echo "mem0 plugin: dependency installation failed (by another session)" >&2
    fi
  fi
fi
