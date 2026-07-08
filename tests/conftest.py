"""Pytest session setup for Study Demo CI and local runs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

for path in (ROOT, SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

parts = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
for path in (ROOT, SRC):
    text = str(path)
    if text not in parts:
        parts.insert(0, text)
os.environ["PYTHONPATH"] = os.pathsep.join(parts)
os.environ.setdefault("V9_UI_MODE", "simple")
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
os.environ.setdefault("DISABLE_EXTERNAL_API", "true")
