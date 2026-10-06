"""Pipeline reprodutível de avaliação do experimento C1--C6."""

from __future__ import annotations

import sys
from pathlib import Path


VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))
