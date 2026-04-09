#!/bin/bash
set -e

BRANCH="websocket-test"
BASE_URL="https://raw.githubusercontent.com/vast-ai/vast-cli/refs/heads/${BRANCH}/examples/websocket"

pip install vastai

curl -s "$BASE_URL/server.py" -o /opt/server.py
curl -s "$BASE_URL/worker.py" -o /opt/worker.py

touch /var/log/ws_server.log

python3 /opt/server.py &
python3 /opt/worker.py
