#!/bin/zsh
set -e

cd "$(dirname "$0")"

PYTHON="python3"

if ! "$PYTHON" -c "import streamlit, PIL, Crypto, requests" >/dev/null 2>&1; then
  if [[ ! -x ".venv/bin/python" ]]; then
    python3 -m venv .venv
  fi
  .venv/bin/python -m pip install -r requirements.txt
  PYTHON=".venv/bin/python"
fi

exec "$PYTHON" -m streamlit run app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --browser.gatherUsageStats false
