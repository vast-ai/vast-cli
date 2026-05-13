#!/bin/bash
#
# Backwards-compatibility test: compare current production vastai CLI
# against the dev build. Tests both --help interface and read-only commands.
#
# Usage:
#   bash tests/compat_test.sh /path/to/dev.whl [--api-key KEY]
#

set -uo pipefail

usage() {
    echo "Usage: bash tests/compat_test.sh /path/to/vastai-dev.whl [--api-key KEY]"
    echo "       (API key may also be provided via VAST_API_KEY env var)"
}

DEV_WHL=""
API_KEY="${VAST_API_KEY:-}"

while [ $# -gt 0 ]; do
    case "$1" in
        --api-key)
            if [ $# -lt 2 ]; then
                echo "error: --api-key requires a value" >&2
                usage
                exit 1
            fi
            API_KEY="$2"
            shift 2
            ;;
        --api-key=*)
            API_KEY="${1#--api-key=}"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo "error: unknown flag: $1" >&2
            usage
            exit 1
            ;;
        *)
            if [ -z "$DEV_WHL" ]; then
                DEV_WHL="$1"
            else
                echo "error: unexpected positional arg: $1" >&2
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

if [ -z "$DEV_WHL" ] || [ ! -f "$DEV_WHL" ]; then
    usage
    exit 1
fi

# Halt on failures during environment setup; individual CLI comparisons later
# capture exit codes explicitly, so we deliberately do not use a global set -e.
fail_setup() {
    echo "error: $1" >&2
    exit 1
}

PROD_VENV="/tmp/vastai-compat-prod"
DEV_VENV="/tmp/vastai-compat-dev"
RESULTS_DIR="/tmp/vastai-compat-results"

rm -rf "$PROD_VENV" "$DEV_VENV" "$RESULTS_DIR"
mkdir -p "$RESULTS_DIR/prod/help" "$RESULTS_DIR/dev/help"
mkdir -p "$RESULTS_DIR/prod/output" "$RESULTS_DIR/dev/output"
mkdir -p "$RESULTS_DIR/diffs"

echo "========================================"
echo "Setting up environments"
echo "========================================"

echo "  Creating prod venv..."
python3 -m venv "$PROD_VENV" || fail_setup "failed to create prod venv at $PROD_VENV"
source "$PROD_VENV/bin/activate"
pip install --quiet vastai 2>&1 | tail -1
[ "${PIPESTATUS[0]}" -eq 0 ] || fail_setup "pip install vastai (prod) failed"
PROD_VERSION=$(vastai --version 2>&1 || echo "unknown")
deactivate
echo "  Prod version: $PROD_VERSION"

echo "  Creating dev venv..."
python3 -m venv "$DEV_VENV" || fail_setup "failed to create dev venv at $DEV_VENV"
source "$DEV_VENV/bin/activate"
pip install --quiet "$DEV_WHL" 2>&1 | tail -1
[ "${PIPESTATUS[0]}" -eq 0 ] || fail_setup "pip install $DEV_WHL (dev) failed"
DEV_VERSION=$(vastai --version 2>&1 || echo "unknown")
deactivate
echo "  Dev version: $DEV_VERSION"

# All two-word commands extracted from the CLI
COMMANDS=(
    "show instances"
    "show instance"
    "create instance"
    "create instances"
    "destroy instance"
    "destroy instances"
    "start instance"
    "start instances"
    "stop instance"
    "stop instances"
    "reboot instance"
    "recycle instance"
    "update instance"
    "label instance"
    "prepay instance"
    "change bid"
    "launch instance"
    "search offers"
    "search benchmarks"
    "search templates"
    "search invoices"
    "create template"
    "update template"
    "delete template"
    "show machine"
    "show machines"
    "show maints"
    "show network-disks"
    "list machine"
    "list machines"
    "unlist machine"
    "delete machine"
    "cleanup machine"
    "defrag machines"
    "set min-bid"
    "set defjob"
    "remove defjob"
    "schedule maint"
    "cancel maint"
    "add network-disk"
    "self-test machine"
    "create team"
    "destroy team"
    "create team-role"
    "show team-role"
    "show team-roles"
    "update team-role"
    "remove team-role"
    "invite member"
    "show members"
    "remove member"
    "create api-key"
    "show api-key"
    "show api-keys"
    "delete api-key"
    "reset api-key"
    "create ssh-key"
    "show ssh-keys"
    "delete ssh-key"
    "update ssh-key"
    "attach ssh"
    "detach ssh"
    "create endpoint"
    "show endpoints"
    "update endpoint"
    "delete endpoint"
    "get endpt-logs"
    "create workergroup"
    "show workergroups"
    "update workergroup"
    "delete workergroup"
    "get wrkgrp-logs"
    "show invoices"
    "show earnings"
    "show deposit"
    "show user"
    "set user"
    "show subaccounts"
    "create subaccount"
    "show ipaddrs"
    "transfer credit"
    "show scheduled-jobs"
    "delete scheduled-job"
    "cancel copy"
    "cancel sync"
    "cloud copy"
    "show connections"
    "search volumes"
    "search network-volumes"
    "create volume"
    "create network-volume"
    "delete volume"
    "clone volume"
    "show volumes"
    "list volume"
    "list volumes"
    "list network-volume"
    "unlist volume"
    "unlist network-volume"
    "show audit-logs"
    "show env-vars"
    "create env-var"
    "update env-var"
    "delete env-var"
    "tfa activate"
    "tfa delete"
    "tfa login"
    "tfa resend-sms"
    "tfa regen-codes"
    "tfa send-sms"
    "tfa send-email"
    "tfa auth-new"
    "tfa status"
    "tfa totp-setup"
    "tfa update"
    "show deployments"
    "show deployment"
    "delete deployment"
    "take snapshot"
)

# Read-only commands safe to run with a real API key
READONLY_COMMANDS=(
    "show instances"
    "show machines"
    "show user"
    "show api-keys"
    "show ssh-keys"
    "show endpoints"
    "show workergroups"
    "show volumes"
    "show connections"
    "show env-vars"
    "show subaccounts"
    "show deployments"
    "show team-roles"
    "show members"
    "show audit-logs"
    "show scheduled-jobs"
    "search offers"
)

HELP_PASS=0
HELP_FAIL=0
HELP_NEW=0
HELP_REMOVED=0
OUTPUT_PASS=0
OUTPUT_FAIL=0
OUTPUT_SKIP=0

echo ""
echo "========================================"
echo "PHASE 1: --help interface compatibility"
echo "========================================"

for cmd in "${COMMANDS[@]}"; do
    safe_name=$(echo "$cmd" | tr ' ' '_')

    # Get prod help
    source "$PROD_VENV/bin/activate"
    vastai $cmd --help > "$RESULTS_DIR/prod/help/$safe_name.txt" 2>&1
    prod_exit=$?
    deactivate

    # Get dev help
    source "$DEV_VENV/bin/activate"
    vastai $cmd --help > "$RESULTS_DIR/dev/help/$safe_name.txt" 2>&1
    dev_exit=$?
    deactivate

    if [ $prod_exit -ne 0 ] && [ $dev_exit -eq 0 ]; then
        echo "  NEW:     $cmd (not in prod, added in dev)"
        HELP_NEW=$((HELP_NEW + 1))
    elif [ $prod_exit -eq 0 ] && [ $dev_exit -ne 0 ]; then
        echo "  REMOVED: $cmd (in prod, missing in dev)"
        HELP_REMOVED=$((HELP_REMOVED + 1))
    elif diff -q "$RESULTS_DIR/prod/help/$safe_name.txt" "$RESULTS_DIR/dev/help/$safe_name.txt" > /dev/null 2>&1; then
        echo "  PASS:    $cmd"
        HELP_PASS=$((HELP_PASS + 1))
    else
        echo "  DIFF:    $cmd"
        diff -u "$RESULTS_DIR/prod/help/$safe_name.txt" "$RESULTS_DIR/dev/help/$safe_name.txt" > "$RESULTS_DIR/diffs/${safe_name}_help.diff" 2>&1
        HELP_FAIL=$((HELP_FAIL + 1))
    fi
done

echo ""
echo "Help results: $HELP_PASS identical, $HELP_FAIL changed, $HELP_NEW new, $HELP_REMOVED removed"

if [ -n "$API_KEY" ]; then
    echo ""
    echo "========================================"
    echo "PHASE 2: Read-only output comparison"
    echo "========================================"

    for cmd in "${READONLY_COMMANDS[@]}"; do
        safe_name=$(echo "$cmd" | tr ' ' '_')

        # Get prod output (flags must come after subcommand in prod)
        source "$PROD_VENV/bin/activate"
        timeout 30 vastai $cmd --api-key "$API_KEY" --raw > "$RESULTS_DIR/prod/output/$safe_name.txt" 2>&1
        prod_exit=$?
        deactivate

        # Get dev output (flags after subcommand for consistency)
        source "$DEV_VENV/bin/activate"
        timeout 30 vastai $cmd --api-key "$API_KEY" --raw > "$RESULTS_DIR/dev/output/$safe_name.txt" 2>&1
        dev_exit=$?
        deactivate

        if [ $prod_exit -ne 0 ] && [ $dev_exit -ne 0 ]; then
            echo "  SKIP:    $cmd (both errored — may need args or permissions)"
            OUTPUT_SKIP=$((OUTPUT_SKIP + 1))
        elif diff -q "$RESULTS_DIR/prod/output/$safe_name.txt" "$RESULTS_DIR/dev/output/$safe_name.txt" > /dev/null 2>&1; then
            echo "  PASS:    $cmd"
            OUTPUT_PASS=$((OUTPUT_PASS + 1))
        else
            echo "  DIFF:    $cmd"
            diff -u "$RESULTS_DIR/prod/output/$safe_name.txt" "$RESULTS_DIR/dev/output/$safe_name.txt" > "$RESULTS_DIR/diffs/${safe_name}_output.diff" 2>&1
            OUTPUT_FAIL=$((OUTPUT_FAIL + 1))
        fi
    done

    echo ""
    echo "Output results: $OUTPUT_PASS identical, $OUTPUT_FAIL changed, $OUTPUT_SKIP skipped"
else
    echo ""
    echo "PHASE 2 SKIPPED: No API key provided."
    echo "  Re-run with: bash tests/compat_test.sh $DEV_WHL --api-key YOUR_KEY"
    echo "  Or set VAST_API_KEY env var."
fi

echo ""
echo "========================================"
echo "SUMMARY"
echo "========================================"
echo "  Help:   $HELP_PASS pass, $HELP_FAIL changed, $HELP_NEW new, $HELP_REMOVED removed"
if [ -n "$API_KEY" ]; then
    echo "  Output: $OUTPUT_PASS pass, $OUTPUT_FAIL changed, $OUTPUT_SKIP skipped"
fi
echo ""
echo "Diffs saved to: $RESULTS_DIR/diffs/"
echo "Full outputs:   $RESULTS_DIR/prod/ and $RESULTS_DIR/dev/"

TOTAL_FAIL=$((HELP_FAIL + HELP_REMOVED + OUTPUT_FAIL))
[ "$TOTAL_FAIL" -eq 0 ] && exit 0 || exit 1
