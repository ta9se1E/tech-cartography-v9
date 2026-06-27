"""Research theme profile export (Phase 27Q.1)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.runtime.v8_research_theme_schema import ResearchThemeProfile
from tech_cartography.services.v8_research_theme_defaults import save_research_theme_profile
from tech_cartography.services.v8_sources_table import project_root_from_here

LOCAL_RESEARCH_THEME = "local_v8_research_theme"


def export_research_theme_profile(
  profile: ResearchThemeProfile,
  project_root: Path | str | None = None,
) -> Path:
  root = Path(project_root or project_root_from_here())
  case_path = save_research_theme_profile(profile, root)
  export_dir = root / "outputs" / LOCAL_RESEARCH_THEME / profile.case_id
  export_dir.mkdir(parents=True, exist_ok=True)
  export_path = export_dir / "research_theme_profile.json"
  export_path.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
  return export_path
