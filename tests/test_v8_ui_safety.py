"""Safety tests for v8 user-facing UI modules (Phase 27B)."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

USER_FACING_UI = (
  "src/tech_cartography/ui/v8_intro_ui.py",
  "src/tech_cartography/ui/v8_input_ui.py",
  "src/tech_cartography/ui/v8_sources_ui.py",
  "src/tech_cartography/ui/v8_patent_shortlist_ui.py",
  "src/tech_cartography/ui/v8_claim_map_ui.py",
  "src/tech_cartography/ui/v8_evidence_map_ui.py",
  "src/tech_cartography/ui/v8_gap_next_actions_ui.py",
  "src/tech_cartography/ui/v8_fixed_point_observation_ui.py",
  "src/tech_cartography/ui/v8_export_ui.py",
)

FORBIDDEN = ("SMTP_PASSWORD", "TAVILY_API_KEY", "eyJhbGci")


def test_user_facing_v8_ui_has_safety_notices() -> None:
  blob = "\n".join((PROJECT_ROOT / rel).read_text(encoding="utf-8") for rel in USER_FACING_UI)
  lowered = blob.lower()
  assert "fto" in lowered or "侵害" in blob
  assert "candidate" in lowered or "候補" in blob


def test_user_facing_v8_ui_no_secret_literals() -> None:
  for rel in USER_FACING_UI:
    text = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
    for token in FORBIDDEN:
      assert token not in text, f"{rel} contains {token}"


def test_v8_ui_modules_have_render_functions() -> None:
  modules = {
    "v8_intro_ui": "render_v8_intro_tab",
    "v8_input_ui": "render_v8_input_tab",
    "v8_sources_ui": "render_v8_sources_tab",
    "v8_patent_shortlist_ui": "render_v8_patent_shortlist_tab",
    "v8_claim_map_ui": "render_v8_claim_map_tab",
    "v8_evidence_map_ui": "render_v8_evidence_map_tab",
    "v8_gap_next_actions_ui": "render_v8_gap_next_actions_tab",
    "v8_fixed_point_observation_ui": "render_v8_fixed_point_observation_tab",
    "v8_export_ui": "render_v8_export_tab",
    "v8_admin_settings_ui": "render_v8_admin_settings_tab",
  }
  for module_name, fn_name in modules.items():
    mod = __import__(f"tech_cartography.ui.{module_name}", fromlist=[fn_name])
    assert callable(getattr(mod, fn_name))
