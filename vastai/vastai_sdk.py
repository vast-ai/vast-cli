"""
Backwards-compatibility shim for ``from vastai.vastai_sdk import VastAI``.

The canonical import path is now ``from vastai.sdk import VastAI``
(or simply ``from vastai import VastAI``).
"""

import warnings

warnings.warn(
    "Importing from 'vastai.vastai_sdk' is deprecated. "
    "Use 'from vastai import VastAI' or 'from vastai.sdk import VastAI' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .sdk import *  # noqa: F401,F403
from .sdk import VastAI  # explicit re-export for type checkers
