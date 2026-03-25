#!/bin/bash
#
# Integration tests for verifying that `pip install vastai` and `pip install vastai-sdk`
# produce identical behavior, and that install/uninstall scenarios are clean.
#
# Prerequisites:
#   - Python 3.9+ available as `python3`
#   - Built wheels placed in the locations below (or override via env vars)
#
# Usage:
#   # 1. Build both wheels from the repo root:
#   python3 -m build --wheel                          # builds dist/vastai-*.whl
#   cd sdk-wrapper && python3 -m build --wheel && cd ..  # builds sdk-wrapper/dist/vastai_sdk-*.whl
#
#   # 2. Run the tests:
#   bash tests/pip_install/test_install_scenarios.sh
#
#   # Or override wheel paths:
#   VASTAI_WHL=/path/to/vastai.whl SDK_WHL=/path/to/vastai_sdk.whl bash tests/pip_install/test_install_scenarios.sh

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VASTAI_WHL="${VASTAI_WHL:-$(ls "$REPO_ROOT"/dist/vastai-*.whl 2>/dev/null | head -1)}"
SDK_WHL="${SDK_WHL:-$(ls "$REPO_ROOT"/sdk-wrapper/dist/vastai_sdk-*.whl 2>/dev/null | head -1)}"

if [ -z "$VASTAI_WHL" ] || [ ! -f "$VASTAI_WHL" ]; then
    echo "ERROR: vastai wheel not found. Build it first: python3 -m build --wheel"
    exit 1
fi
if [ -z "$SDK_WHL" ] || [ ! -f "$SDK_WHL" ]; then
    echo "ERROR: vastai-sdk wheel not found. Build it first: cd sdk-wrapper && python3 -m build --wheel"
    exit 1
fi

echo "Using wheels:"
echo "  vastai:     $VASTAI_WHL"
echo "  vastai-sdk: $SDK_WHL"
echo ""

PASS=0
FAIL=0
ENVNUM=0

check() {
    local desc="$1"; local cmd="$2"; local expect="$3"
    if eval "$cmd" > /dev/null 2>&1; then result="ok"; else result="fail"; fi
    if [ "$result" = "$expect" ]; then
        echo "  PASS: $desc"; PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc (expected=$expect got=$result)"; FAIL=$((FAIL + 1))
    fi
}

new_env() {
    ENVNUM=$((ENVNUM + 1))
    local envdir="/tmp/vastai-pip-test-$ENVNUM"
    rm -rf "$envdir"
    python3 -m venv "$envdir"
    source "$envdir/bin/activate"
}

cleanup() {
    for i in $(seq 1 $ENVNUM); do
        rm -rf "/tmp/vastai-pip-test-$i"
    done
}
trap cleanup EXIT

echo "========================================"
echo "SCENARIO 1: pip install vastai only"
echo "========================================"
new_env
pip install "$VASTAI_WHL" > /dev/null 2>&1
check "import vastai"                 "python3 -c 'import vastai'"                               "ok"
check "import vastai_sdk"             "python3 -c 'import vastai_sdk'"                           "ok"
check "from vastai import VastAI"     "python3 -c 'from vastai import VastAI'"                   "ok"
check "from vastai_sdk import VastAI" "python3 -c 'from vastai_sdk import VastAI'"               "ok"
check "CLI entry point"               "python3 -c 'from vastai.cli.main import main'"            "ok"
check "vastai_sdk is vastai"          "python3 -c 'import vastai, vastai_sdk; assert vastai.VastAI is vastai_sdk.VastAI'" "ok"
deactivate
echo ""

echo "========================================"
echo "SCENARIO 2: pip install vastai + vastai-sdk"
echo "========================================"
new_env
pip install "$VASTAI_WHL" > /dev/null 2>&1
pip install --no-deps "$SDK_WHL" > /dev/null 2>&1
check "import vastai"                 "python3 -c 'import vastai'"                               "ok"
check "import vastai_sdk"             "python3 -c 'import vastai_sdk'"                           "ok"
check "from vastai import VastAI"     "python3 -c 'from vastai import VastAI'"                   "ok"
check "from vastai_sdk import VastAI" "python3 -c 'from vastai_sdk import VastAI'"               "ok"
check "CLI entry point"               "python3 -c 'from vastai.cli.main import main'"            "ok"
check "vastai_sdk is vastai"          "python3 -c 'import vastai, vastai_sdk; assert vastai.VastAI is vastai_sdk.VastAI'" "ok"
deactivate
echo ""

echo "========================================"
echo "SCENARIO 3: Both installed, uninstall"
echo "vastai-sdk — everything still works"
echo "========================================"
new_env
pip install "$VASTAI_WHL" > /dev/null 2>&1
pip install --no-deps "$SDK_WHL" > /dev/null 2>&1
pip uninstall -y vastai-sdk > /dev/null 2>&1
check "vastai still installed"        "pip show vastai"                                          "ok"
check "vastai-sdk removed"            "pip show vastai-sdk"                                      "fail"
check "import vastai"                 "python3 -c 'import vastai'"                               "ok"
check "import vastai_sdk still works" "python3 -c 'import vastai_sdk'"                           "ok"
check "from vastai_sdk import VastAI" "python3 -c 'from vastai_sdk import VastAI'"               "ok"
check "CLI entry point"               "python3 -c 'from vastai.cli.main import main'"            "ok"
deactivate
echo ""

echo "========================================"
echo "SCENARIO 4: Both installed, uninstall"
echo "vastai — imports break as expected"
echo "========================================"
new_env
pip install "$VASTAI_WHL" > /dev/null 2>&1
pip install --no-deps "$SDK_WHL" > /dev/null 2>&1
pip uninstall -y vastai > /dev/null 2>&1
check "vastai removed"                "pip show vastai"                                          "fail"
check "vastai-sdk still listed"       "pip show vastai-sdk"                                      "ok"
check "import vastai fails"           "python3 -c 'import vastai'"                               "fail"
check "import vastai_sdk fails"       "python3 -c 'import vastai_sdk'"                           "fail"
deactivate
echo ""

echo "========================================"
echo "SCENARIO 5: Only vastai, uninstall — clean"
echo "========================================"
new_env
pip install "$VASTAI_WHL" > /dev/null 2>&1
pip uninstall -y vastai > /dev/null 2>&1
check "vastai removed"                "pip show vastai"                                          "fail"
check "import vastai fails"           "python3 -c 'import vastai'"                               "fail"
check "import vastai_sdk fails"       "python3 -c 'import vastai_sdk'"                           "fail"
deactivate
echo ""

echo "========================================"
echo "SCENARIO 6: File ownership — both packages"
echo "claim vastai_sdk/ (expected, files identical)"
echo "========================================"
new_env
pip install "$VASTAI_WHL" > /dev/null 2>&1
pip install --no-deps "$SDK_WHL" > /dev/null 2>&1
VASTAI_HAS=$(pip show -f vastai 2>/dev/null | grep "vastai_sdk/" || true)
SDK_HAS=$(pip show -f vastai-sdk 2>/dev/null | grep "vastai_sdk/" || true)
if [ -n "$VASTAI_HAS" ]; then
    echo "  PASS: vastai claims vastai_sdk/ — expected"
    PASS=$((PASS + 1))
else
    echo "  FAIL: vastai does NOT claim vastai_sdk/"
    FAIL=$((FAIL + 1))
fi
if [ -n "$SDK_HAS" ]; then
    echo "  INFO: vastai-sdk also claims vastai_sdk/ — acceptable (identical files)"
else
    echo "  INFO: vastai-sdk does not claim vastai_sdk/"
fi
deactivate
echo ""

echo "========================================"
echo "RESULTS: $PASS passed, $FAIL failed"
echo "========================================"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
