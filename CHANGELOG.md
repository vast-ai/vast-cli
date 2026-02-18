# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **SDK Integration**: `VastAI` class now imports from live `vast.py` module instead of frozen copy
- **Type Hints**: Complete type annotations on all 130+ SDK methods in `vastai_base.py`
- **Type Hints**: Return type annotations distinguishing `list[dict]` vs `dict` returns
- **Docstrings**: All public SDK methods have docstrings for IDE autocomplete
- **Serverless Lazy Imports**: Serverless classes load on-demand via PEP 562 `__getattr__`
- **Test Suite**: 547 tests covering HTTP helpers, timezone, query parser, SDK wrapper, CLI commands
- **Static Analysis**: mypy configuration with strict mode for `vastai/` package
- **Linting**: Ruff configuration with pre-commit hooks
- **Retry Logic**: Expanded retry to handle 429, 502, 503, 504 status codes and connection errors
- **Timeout Handling**: All HTTP requests now have configurable timeouts (30s default, 120s for file ops)
- **DRY Helpers**: `api_call()`, `output_result()`, `error_output()`, `require_id()` helpers
- **Backwards Compatibility**: `autogroup_*` aliases for renamed `workergroup_*` methods

### Changed

- **Import Path**: Primary import is now `from vastai import VastAI` (was `from vastai_sdk import VastAI`)
- **Package Structure**: SDK, CLI, and serverless unified in single `vastai` package
- **UTC Handling**: All timestamp functions use `datetime.fromtimestamp(ts, tz=timezone.utc)` instead of deprecated `utcfromtimestamp()`
- **Error Output**: Error messages are JSON in `--raw` mode for machine-readable scripting
- **Dict Access**: Safe `.get()` patterns on all API response handling (50+ locations)
- **Subprocess**: All subprocess calls use argument lists instead of `shell=True`
- **Exception Handling**: Specific exception types replace bare `except:` clauses

### Fixed

- **Mutable Defaults**: Fixed `json={}` mutable default arguments in `http_put`, `http_post`, `http_del`
- **Timezone Bugs**: Fixed local time displayed as "UTC" - now uses actual UTC conversion
- **Raw Mode**: Fixed 31+ functions returning `Response` objects instead of parsed JSON
- **Query Parser**: Fixed field alias bug where `v` referenced already-popped dict key
- **Instance Display**: Fixed `show__instances()` loop not storing modified rows back to list
- **Machine Display**: Fixed `show__machine()` to handle single dict response (not just list)
- **Search Functions**: Fixed hardcoded `if True:` in `search__benchmarks`, `search__invoices`, `search__templates`
- **SDK Import**: Fixed missing `timezone` import from `datetime` module
- **SDK Exceptions**: Fixed overly broad `except: pass` that swallowed errors silently
- **SDK stdout**: Fixed stdout capture to restore in `finally` block (thread-safe)
- **SDK sys.exit**: CLI `sys.exit()` calls now caught and converted to return values
- **Variable Shadowing**: Renamed `id` and `sum` local variables to avoid shadowing builtins
- **API Key Handling**: Removed redundant API key from JSON body in 4 serverless functions
- **Cluster Display**: Clusters without manager node now skipped gracefully
- **Typo Fixes**: Fixed `reuqest_idx` typo in serverless client, `debbuging` typo in Namespace

### Deprecated

- `from vastai_sdk import VastAI` import path - use `from vastai import VastAI`
- `autogroup` command names - use `workergroup` (aliases remain for compatibility)

### Removed

- Frozen copy of `vast.py` in SDK (SDK now imports from live module)
- Unused dependencies: `fastapi`, `uvicorn`, `jsonschema`, `nltk`, `transformers`, `hf_transfer`
- Dead code: unreachable `else` branches after `raise_for_status()`
- Undocumented `--transfer_credit` flag from `create team` command

### Security

- Removed `shell=True` from SSH/SCP subprocess calls (command injection risk)
- API requests no longer include key in JSON body when header auth is used

## [0.x.x] - Previous Releases

See [GitHub Releases](https://github.com/vast-ai/vast-cli/releases) for prior version history.
