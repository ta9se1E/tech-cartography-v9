"""Ensure deprecated Streamlit use_container_width is migrated to width (Phase 27B.1)."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCAN_ROOTS = (
  PROJECT_ROOT / "app.py",
  PROJECT_ROOT / "src",
  PROJECT_ROOT / "tests",
)

# Paths may mention the old API in migration docs/tests only with explicit allowlist.
ALLOWLIST: dict[str, str] = {
  "tests/test_streamlit_width_deprecation.py": "migration guard test references deprecated name",
  "scripts/check_v8_reframe_ready.py": "readiness check scans for deprecated pattern",
}

DEPRECATED_PATTERN = re.compile(r"use_container_width\s*=")


def _iter_python_files(root: Path) -> list[Path]:
  if root.is_file() and root.suffix == ".py":
    return [root]
  if not root.is_dir():
    return []
  return sorted(root.rglob("*.py"))


def find_deprecated_width_usage() -> list[tuple[str, int, str]]:
  hits: list[tuple[str, int, str]] = []
  for scan_root in SCAN_ROOTS:
    for path in _iter_python_files(scan_root):
      rel = str(path.relative_to(PROJECT_ROOT))
      if rel in ALLOWLIST:
        continue
      text = path.read_text(encoding="utf-8")
      for line_no, line in enumerate(text.splitlines(), start=1):
        if DEPRECATED_PATTERN.search(line):
          hits.append((rel, line_no, line.strip()))
  return hits


def test_no_use_container_width_in_app_src_tests() -> None:
  hits = find_deprecated_width_usage()
  assert not hits, "deprecated use_container_width= remains:\n" + "\n".join(
    f"  {path}:{line}: {content}" for path, line, content in hits
  )


def test_app_py_uses_width_stretch_for_sidebar_button() -> None:
  text = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
  assert 'width="stretch"' in text
  assert "use_container_width" not in text


def test_easy_japanese_ui_dataframe_uses_width() -> None:
  text = (PROJECT_ROOT / "src/tech_cartography/ui/easy_japanese_ui.py").read_text(encoding="utf-8")
  assert 'width="stretch"' in text
  assert "use_container_width" not in text
