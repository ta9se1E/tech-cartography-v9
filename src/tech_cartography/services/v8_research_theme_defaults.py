"""Default structured research theme profiles (Phase 27Q.1)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.runtime.v8_research_theme_schema import ResearchThemeProfile
from tech_cartography.services.v8_sources_table import project_root_from_here

CASE_01_PAN_PRECURSOR_DEFECT_THEME = ResearchThemeProfile(
  case_id="case_01_pan_graphitization",
  theme_name="PAN系炭素繊維前駆体の表面・内部欠陥制御",
  theme_description=(
    "PAN系炭素繊維前駆体における表面欠陥、内部ボイド、ゲル状異物、毛羽、単糸間融着、"
    "乾燥緻密化、凝固・延伸・乾燥工程条件と、最終炭素繊維の強度低下・品位低下との関係を調べる。"
  ),
  core_keywords=[
    "PAN carbon fiber precursor",
    "polyacrylonitrile precursor fiber",
    "acrylic precursor fiber",
    "carbon fiber precursor fiber",
    "surface defect",
    "internal defect",
    "internal void",
    "microvoid",
    "void",
    "pore",
    "porosity",
    "surface roughness",
    "fibril",
    "skin layer",
    "gel",
    "gel-like foreign matter",
    "contaminant",
    "impurity",
    "fuzz",
    "broken filament",
    "filament fusion",
    "densification",
    "dry densification",
  ],
  application_keywords=[
    "high tensile strength carbon fiber",
    "high strength carbon fiber",
    "high modulus carbon fiber",
    "CFRP",
    "composite reinforcement",
    "aerospace",
    "aircraft",
    "automotive",
    "pressure vessel",
    "hydrogen tank",
    "wind turbine blade",
    "structural material",
    "quality stabilization",
    "process stability",
    "strand strength",
  ],
  material_process_keywords=[
    "acrylonitrile",
    "itaconic acid",
    "methacrylic acid",
    "PAN copolymer",
    "carboxyl group",
    "carboxylic acid reaction index",
    "DMSO",
    "dimethyl sulfoxide",
    "DMF",
    "dimethylformamide",
    "DMAc",
    "dimethylacetamide",
    "spinning dope temperature",
    "coagulation bath",
    "coagulation bath temperature",
    "dry-jet wet spinning",
    "wet spinning",
    "air gap",
    "nozzle",
    "spinneret",
    "filtration",
    "degassing",
    "defoaming",
    "washing",
    "oiling",
    "drying",
    "drying heat history",
    "heat history index",
    "stretching",
    "hot water drawing",
    "steam drawing",
    "stabilization",
    "oxidation",
    "carbonization",
  ],
  exclude_keywords=[
    "carbon nanotube",
    "CNT",
    "carbon nanofiber",
    "graphene",
    "recycled carbon fiber",
    "chopped fiber",
    "prepreg molding",
    "resin transfer molding",
    "CFRTP molding",
    "electrode",
    "battery electrode",
    "activated carbon",
    "pitch precursor",
    "lignin precursor",
    "cellulose precursor",
  ],
  seed_publication_numbers=[
    "JP2022090764A",
    "JP2023163084A",
    "JP2018084002A",
    "JP2015030926A",
    "JP2009046770A",
    "JP5141598B2",
  ],
  max_results=1000,
  countries=["JP", "CN", "US", "EP"],
  publication_year_from=2000,
  publication_year_to=None,
  search_mode="seed_and_keywords",
  notes="Phase27Q.1 default — PAN precursor defect control theme",
)

FIRST_TEST_SEED_PUBLICATIONS: tuple[str, ...] = (
  "JP2022090764A",
  "JP2023163084A",
  "JP2018084002A",
)

DEFAULT_THEMES: dict[str, ResearchThemeProfile] = {
  "case_01_pan_graphitization": CASE_01_PAN_PRECURSOR_DEFECT_THEME,
}


def default_theme_for_case(case_id: str) -> ResearchThemeProfile:
  if case_id in DEFAULT_THEMES:
    base = DEFAULT_THEMES[case_id]
    return ResearchThemeProfile.from_dict(base.to_dict())
  return ResearchThemeProfile(case_id=case_id, search_mode="keyword_only")


def research_theme_profile_path(case_id: str, project_root: Path | str | None = None) -> Path:
  root = Path(project_root or project_root_from_here())
  return root / "cases" / case_id / "research_theme_profile.json"


def load_research_theme_profile(
  case_id: str,
  project_root: Path | str | None = None,
) -> ResearchThemeProfile:
  import json

  path = research_theme_profile_path(case_id, project_root)
  if path.exists():
    data = json.loads(path.read_text(encoding="utf-8"))
    data["case_id"] = case_id
    return ResearchThemeProfile.from_dict(data)
  return default_theme_for_case(case_id)


def save_research_theme_profile(
  profile: ResearchThemeProfile,
  project_root: Path | str | None = None,
) -> Path:
  import json

  from tech_cartography.runtime.v8_sources_schema import utc_now_iso

  root = Path(project_root or project_root_from_here())
  path = research_theme_profile_path(profile.case_id, root)
  path.parent.mkdir(parents=True, exist_ok=True)
  profile.updated_at = utc_now_iso()
  path.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
  return path
