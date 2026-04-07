#!/bin/bash

set -e -o pipefail

WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"

SERVER_DIR="$WORKSPACE_DIR/vast-pyworker"
ENV_PATH="$WORKSPACE_DIR/worker-env"
DEBUG_LOG="$WORKSPACE_DIR/debug.log"
PYWORKER_LOG="$WORKSPACE_DIR/pyworker.log"

REPORT_ADDR="${REPORT_ADDR:-https://run.vast.ai}"
USE_SSL="${USE_SSL:-true}"
WORKER_PORT="${WORKER_PORT:-3000}"
mkdir -p "$WORKSPACE_DIR"
cd "$WORKSPACE_DIR"

exec &> >(tee -a "$DEBUG_LOG")

function echo_var(){
    echo "$1: ${!1}"
}

function report_error_and_exit(){
    local error_msg="$1"
    echo "ERROR: $error_msg"

    MTOKEN="${MASTER_TOKEN:-}"
    VERSION="${PYWORKER_VERSION:-0}"

    IFS=',' read -r -a REPORT_ADDRS <<< "${REPORT_ADDR}"
    for addr in "${REPORT_ADDRS[@]}"; do
        curl -sS -X POST -H 'Content-Type: application/json' \
            -d "$(cat <<JSON
{
  "id": ${CONTAINER_ID:-0},
  "mtoken": "${MTOKEN}",
  "version": "${VERSION}",
  "error_msg": "${error_msg}",
  "url": "${URL:-}"
}
JSON
)" "${addr%/}/worker_status/" || true
    done

    exit 1
}

function install_vastai_sdk() {
    # If SDK_BRANCH is set, install vastai-sdk from the vast-sdk repo at that branch/tag/commit.
    if [ -n "${SDK_BRANCH:-}" ]; then
        if [ -n "${SDK_VERSION:-}" ]; then
            echo "WARNING: Both SDK_BRANCH and SDK_VERSION are set; using SDK_BRANCH=${SDK_BRANCH}"
        fi
        echo "Installing vastai-sdk from https://github.com/vast-ai/vast-sdk/ @ ${SDK_BRANCH}"
        if ! uv pip install "vastai-sdk @ git+https://github.com/vast-ai/vast-sdk.git@${SDK_BRANCH}"; then
            report_error_and_exit "Failed to install vastai-sdk from vast-ai/vast-sdk@${SDK_BRANCH}"
        fi
        return 0
    fi

    if [ -n "${SDK_VERSION:-}" ]; then
        echo "Installing vastai-sdk version ${SDK_VERSION}"
        if ! uv pip install "vastai-sdk==${SDK_VERSION}"; then
            report_error_and_exit "Failed to install vastai-sdk==${SDK_VERSION}"
        fi
        return 0
    fi

    echo "Installing default vastai-sdk"
    if ! uv pip install vastai-sdk; then
        report_error_and_exit "Failed to install vastai-sdk"
    fi
}

[ -n "$BACKEND" ] && [ -z "$HF_TOKEN" ] && report_error_and_exit "HF_TOKEN must be set when BACKEND is set!"
[ -z "$CONTAINER_ID" ] && report_error_and_exit "CONTAINER_ID must be set!"
[ "$BACKEND" = "comfyui" ] && [ -z "$COMFY_MODEL" ] && report_error_and_exit "For comfyui backends, COMFY_MODEL must be set!"

echo "start_server.sh"
date

echo_var BACKEND
echo_var REPORT_ADDR
echo_var WORKER_PORT
echo_var WORKSPACE_DIR
echo_var SERVER_DIR
echo_var ENV_PATH
echo_var DEBUG_LOG
echo_var PYWORKER_LOG
echo_var MODEL_LOG

if [ -e "$MODEL_LOG" ]; then
    echo "Rotating model log at $MODEL_LOG to $MODEL_LOG.old"
    if ! cat "$MODEL_LOG" >> "$MODEL_LOG.old"; then
        report_error_and_exit "Failed to rotate model log"
    fi
    if ! : > "$MODEL_LOG"; then
        report_error_and_exit "Failed to truncate model log"
    fi
fi

# Populate /etc/environment with quoted values
if ! grep -q "VAST" /etc/environment; then
    if ! env -0 | grep -zEv "^(HOME=|SHLVL=)|CONDA" | while IFS= read -r -d '' line; do
            name=${line%%=*}
            value=${line#*=}
            printf '%s="%s"\n' "$name" "$value"
        done > /etc/environment; then
        echo "WARNING: Failed to populate /etc/environment, continuing anyway"
    fi
fi

if [ ! -d "$ENV_PATH" ]
then
    echo "setting up venv"
    if ! which uv; then
        if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
            report_error_and_exit "Failed to install uv package manager"
        fi
        if [[ -f ~/.local/bin/env ]]; then
            if ! source ~/.local/bin/env; then
                report_error_and_exit "Failed to source uv environment"
            fi
        else
            echo "WARNING: ~/.local/bin/env not found after uv installation"
        fi
    fi

    if [[ ! -d $SERVER_DIR ]]; then
        if ! git clone "${PYWORKER_REPO:-https://github.com/vast-ai/pyworker}" "$SERVER_DIR"; then
            report_error_and_exit "Failed to clone pyworker repository"
        fi
    fi
    if [[ -n ${PYWORKER_REF:-} ]]; then
        if ! (cd "$SERVER_DIR" && git checkout "$PYWORKER_REF"); then
            report_error_and_exit "Failed to checkout pyworker reference: $PYWORKER_REF"
        fi
    fi

    if ! uv venv --python-preference only-managed "$ENV_PATH" -p 3.10; then
        report_error_and_exit "Failed to create virtual environment"
    fi
    
    if ! source "$ENV_PATH/bin/activate"; then
        report_error_and_exit "Failed to activate virtual environment"
    fi

    if ! uv pip install -r "${SERVER_DIR}/requirements.txt"; then
        report_error_and_exit "Failed to install Python requirements"
    fi

    install_vastai_sdk

    if ! touch ~/.no_auto_tmux; then
        report_error_and_exit "Failed to create ~/.no_auto_tmux"
    fi
else
    if [[ -f ~/.local/bin/env ]]; then
        if ! source ~/.local/bin/env; then
            report_error_and_exit "Failed to source uv environment"
        fi
    fi
    if ! source "$WORKSPACE_DIR/worker-env/bin/activate"; then
        report_error_and_exit "Failed to activate existing virtual environment"
    fi
    echo "environment activated"
    echo "venv: $VIRTUAL_ENV"
fi

if [ "$USE_SSL" = true ]; then

    if ! cat << EOF > /etc/openssl-san.cnf
    [req]
    default_bits       = 2048
    distinguished_name = req_distinguished_name
    req_extensions     = v3_req

    [req_distinguished_name]
    countryName         = US
    stateOrProvinceName = CA
    organizationName    = Vast.ai Inc.
    commonName          = vast.ai

    [v3_req]
    basicConstraints = CA:FALSE
    keyUsage         = nonRepudiation, digitalSignature, keyEncipherment
    subjectAltName   = @alt_names

    [alt_names]
    IP.1   = 0.0.0.0
EOF
    then
        report_error_and_exit "Failed to write OpenSSL config"
    fi

    if ! openssl req -newkey rsa:2048 -subj "/C=US/ST=CA/CN=pyworker.vast.ai/" \
        -nodes \
        -sha256 \
        -keyout /etc/instance.key \
        -out /etc/instance.csr \
        -config /etc/openssl-san.cnf; then
        report_error_and_exit "Failed to generate SSL certificate request"
    fi

    if ! curl --header 'Content-Type: application/octet-stream' \
        --data-binary @/etc/instance.csr \
        -X \
        POST "https://console.vast.ai/api/v0/sign_cert/?instance_id=$CONTAINER_ID" > /etc/instance.crt; then
        report_error_and_exit "Failed to sign SSL certificate"
    fi
fi

export REPORT_ADDR WORKER_PORT USE_SSL UNSECURED

if ! cd "$SERVER_DIR"; then
    report_error_and_exit "Failed to cd into SERVER_DIR: $SERVER_DIR"
fi

echo "launching PyWorker server"

set +e

PY_STATUS=1

if [ -f "$SERVER_DIR/worker.py" ]; then
    echo "trying worker.py"
    python3 -m "worker" |& tee -a "$PYWORKER_LOG"
    PY_STATUS=${PIPESTATUS[0]}
fi

if [ "${PY_STATUS}" -ne 0 ] && [ -f "$SERVER_DIR/workers/$BACKEND/worker.py" ]; then
    echo "trying workers.${BACKEND}.worker"
    python3 -m "workers.${BACKEND}.worker" |& tee -a "$PYWORKER_LOG"
    PY_STATUS=${PIPESTATUS[0]}
fi

if [ "${PY_STATUS}" -ne 0 ] && [ -f "$SERVER_DIR/workers/$BACKEND/server.py" ]; then
    echo "trying workers.${BACKEND}.server"
    python3 -m "workers.${BACKEND}.server" |& tee -a "$PYWORKER_LOG"
    PY_STATUS=${PIPESTATUS[0]}
fi

set -e

if [ "${PY_STATUS}" -ne 0 ]; then
    if [ ! -f "$SERVER_DIR/worker.py" ] && [ ! -f "$SERVER_DIR/workers/$BACKEND/worker.py" ] && [ ! -f "$SERVER_DIR/workers/$BACKEND/server.py" ]; then
        report_error_and_exit "Failed to find PyWorker"
    fi
    report_error_and_exit "PyWorker exited with status ${PY_STATUS}"
fi

echo "launching PyWorker server done"
