# pip install integration tests

Verifies that `pip install vastai` and `pip install vastai-sdk` produce identical
behavior across all install/uninstall scenarios.

## Scenarios tested

1. **`pip install vastai` only** — `import vastai` and `import vastai_sdk` both work, CLI present
2. **`pip install vastai` + `pip install vastai-sdk`** — identical to scenario 1
3. **Both installed, uninstall `vastai-sdk`** — everything still works (no file collision)
4. **Both installed, uninstall `vastai`** — both imports correctly break
5. **Only `vastai`, then uninstall** — clean removal, no leftover files
6. **File ownership** — both `vastai` and `vastai-sdk` claim `vastai_sdk/` files (expected, since the files are identical)

## Running

```bash
# 1. Build both wheels from the repo root
pip install build poetry-core
python3 -m build --wheel
cd sdk-wrapper && python3 -m build --wheel && cd ..

# 2. Run the tests
bash tests/pip_install/test_install_scenarios.sh
```

You can also override wheel paths:

```bash
VASTAI_WHL=/path/to/vastai.whl SDK_WHL=/path/to/vastai_sdk.whl \
  bash tests/pip_install/test_install_scenarios.sh
```

Each scenario creates an isolated venv under `/tmp/vastai-pip-test-*`, which are
cleaned up automatically on exit.
