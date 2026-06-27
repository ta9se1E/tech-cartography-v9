"""Phase27Q.1 claim batch import UI tests."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_claim_batch_import_ui as batch_ui


def test_claim_batch_ui_importable() -> None:
  assert callable(batch_ui.render_claim_batch_import_section)


def test_claim_batch_ui_content() -> None:
  text = Path(batch_ui.__file__).read_text(encoding="utf-8")
  assert "請求項CSV/Excel" in text
  assert "manual_input" not in text or "自動生成" in text
  assert "自動生成しません" in text
  assert "use_container_width" not in text
  assert "SMTP_PASSWORD" not in text
