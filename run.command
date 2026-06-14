#!/bin/zsh
set -e

cd "$(dirname "$0")"

if curl --silent --fail http://127.0.0.1:8501/_stcore/health >/dev/null 2>&1; then
  open http://127.0.0.1:8501
  exit 0
fi

PYTHON="python3"

if ! "$PYTHON" -c "import streamlit, PIL, Crypto, requests" >/dev/null 2>&1; then
  if [[ ! -x ".venv/bin/python" ]]; then
    python3 -m venv .venv
  fi
  .venv/bin/python -m pip install -r requirements.txt
  PYTHON=".venv/bin/python"
fi

(sleep 1.5; open http://127.0.0.1:8501) &

exec "$PYTHON" -m streamlit run app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --browser.gatherUsageStats false
