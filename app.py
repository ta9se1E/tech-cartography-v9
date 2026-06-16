"""PatentScout AI v7 entry point."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
  sys.path.insert(0, str(_SRC))

from tech_cartography.ui.streamlit_app import main

if __name__ == "__main__":
  main()
