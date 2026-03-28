#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${1:-config.yaml}"

cd "$ROOT_DIR"

if [[ ! -d ".venv" ]]; then
  echo "[ERROR] .venv not found in $ROOT_DIR" >&2
  echo "Create it first: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "[ERROR] Config not found: $CONFIG_FILE" >&2
  exit 1
fi

exec "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/main.py" --config "$CONFIG_FILE"
