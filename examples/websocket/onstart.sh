#!/bin/bash
set -e

BRANCH="websocket-test"
BASE_URL="https://raw.githubusercontent.com/vast-ai/vast-cli/refs/heads/${BRANCH}/examples/websocket"

# Start the aiohttp server (HTTP + WS) in the background on system python
pip install aiohttp
curl -s "$BASE_URL/server.py" -o /opt/server.py
python3 -u /opt/server.py &

# Set up the pyworker directory with our worker.py and a requirements.txt
# so start_server.sh finds what it needs
mkdir -p /workspace/vast-pyworker
curl -s "$BASE_URL/worker.py" -o /workspace/vast-pyworker/worker.py
curl -s "$BASE_URL/requirements.txt" -o /workspace/vast-pyworker/requirements.txt

# Now let start_server.sh handle the venv, vastai install, and worker launch.
# It will see /workspace/vast-pyworker already exists and skip cloning,
# then install requirements.txt into the venv, install vastai, and run worker.py.
curl -L https://raw.githubusercontent.com/vast-ai/pyworker/refs/heads/main/start_server.sh | bash
