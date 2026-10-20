#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtualenv with python3.11…"
  python3.11 -m venv .venv
fi

source .venv/bin/activate

echo "Installing dependencies (only first time is slow)…"
pip install -q -r requirements.txt

echo "Starting server at http://127.0.0.1:8000"
exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload