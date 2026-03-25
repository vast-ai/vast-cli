# vastai_sdk/__init__.py

# Backward-compatibility shim: allow "import vastai_sdk" to reference "vastai"
import sys
import importlib

# Import the real package
_vastai = importlib.import_module("vastai")

# Register it under the old name
sys.modules[__name__] = _vastai
