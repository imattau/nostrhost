"""Make the nostrhost-protocol library importable for the umbrella's tools tests.

The library lives at libs/nostrhost-protocol/python/src and may not be pip
installed in this checkout; this conftest adds its source tree to sys.path so
tools/tests can import it directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SRC = ROOT / "libs/nostrhost-protocol/python/src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))