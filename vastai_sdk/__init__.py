# vastai_sdk/__init__.py

# Backward-compatibility shim: allow "import vastai_sdk" to reference "vastai"
# This package is deprecated. Use "import vastai" instead.

import sys
import warnings
import importlib

warnings.warn(
    "The 'vastai_sdk' package is deprecated. "
    "Use 'from vastai import VastAI' instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Import the real package
_vastai = importlib.import_module("vastai")

# Register it under the old name so attribute access works
sys.modules[__name__] = _vastai
