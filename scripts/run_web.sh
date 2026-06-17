#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [ ! -f ".env" ]; then
  echo "Missing .env in $PROJECT_DIR" >&2
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Missing virtualenv. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev,ocr]'" >&2
  exit 1
fi

exec .venv/bin/python -m pdf_report_ingestor.cli web --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
