"""Domain term dictionary for Study Demo theme draft mapping."""

from __future__ import annotations

from typing import Any

# Generalized concept dictionary. safe_alias=True entries may be suggested, not auto-accepted.
THEME_TERM_ENTRIES: list[dict[str, Any]] = [
  {
    "canonical_concept": "carbon_fiber_sizing_agent",
    "ja_terms": ["炭素繊維用サイジング剤", "サイジング剤", "炭素繊維", "PAN"],
    "en_terms": ["carbon fiber sizing agent", "carbon fiber tow sizing", "aqueous sizing agent", "aqueous polyurethane"],
    "bucket": "core",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "sizing_composition",
    "ja_terms": ["サイジング剤組成", "組成"],
    "en_terms": ["sizing composition", "composition"],
    "bucket": "material_process",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "sizing_addon",
    "ja_terms": ["付与量", "サイジング剤付着量"],
    "en_terms": ["sizing add-on", "add-on amount"],
    "bucket": "material_process",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "sizing_application",
    "ja_terms": ["塗布"],
    "en_terms": ["sizing application"],
    "bucket": "material_process",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "drying_condition",
    "ja_terms": ["乾燥条件", "乾燥温度"],
    "en_terms": ["drying condition", "drying conditions", "drying temperature"],
    "bucket": "material_process",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "bundling",
    "ja_terms": ["集束性"],
    "en_terms": ["bundling"],
    "bucket": "use_or_property",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "spreading",
    "ja_terms": ["開繊性"],
    "en_terms": ["spreading"],
    "bucket": "use_or_property",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "fuzz",
    "ja_terms": ["毛羽"],
    "en_terms": ["fuzz"],
    "bucket": "use_or_property",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "abrasion_resistance",
    "ja_terms": ["耐擦過性"],
    "en_terms": ["abrasion resistance"],
    "bucket": "use_or_property",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "resin_impregnation",
    "ja_terms": ["樹脂含浸性", "含浸性"],
    "en_terms": ["resin impregnation"],
    "bucket": "use_or_property",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "interfacial_adhesion",
    "ja_terms": ["界面接着性", "界面接着"],
    "en_terms": ["interfacial adhesion"],
    "bucket": "use_or_property",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "tensile_strength",
    "ja_terms": ["引張強度"],
    "en_terms": ["tensile strength"],
    "bucket": "use_or_property",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "tensile_modulus",
    "ja_terms": ["引張弾性率"],
    "en_terms": ["tensile modulus"],
    "bucket": "use_or_property",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "exclude_paper_sizing",
    "ja_terms": [],
    "en_terms": ["paper sizing"],
    "bucket": "exclude",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "exclude_starch_sizing",
    "ja_terms": [],
    "en_terms": ["starch sizing"],
    "bucket": "exclude",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "exclude_activated_carbon",
    "ja_terms": [],
    "en_terms": ["activated carbon"],
    "bucket": "exclude",
    "safe_alias": True,
    "domain": "carbon_fiber_sizing",
  },
  {
    "canonical_concept": "exclude_textile",
    "ja_terms": [],
    "en_terms": ["textile"],
    "bucket": "exclude",
    "safe_alias": True,
    "domain": "general",
  },
]

CANONICAL_DEDUP_GROUPS: dict[str, list[str]] = {
  "resin_impregnation": ["含浸性", "樹脂含浸性", "resin impregnation"],
  "interfacial_adhesion": ["界面接着", "界面接着性", "interfacial adhesion"],
  "sizing_addon": ["sizing add-on", "add-on amount", "付与量", "サイジング剤付着量"],
  "drying_condition": ["drying condition", "drying conditions", "乾燥条件", "乾燥温度"],
}


def iter_dictionary_entries() -> list[dict[str, Any]]:
  return list(THEME_TERM_ENTRIES)


def bucket_to_keyword_key(bucket: str, language: str) -> str:
  mapping = {
    ("core", "ja"): "core_ja",
    ("core", "en"): "core_en",
    ("use_or_property", "ja"): "use_ja",
    ("use_or_property", "en"): "use_en",
    ("material_process", "ja"): "material_process_ja",
    ("material_process", "en"): "material_process_en",
    ("exclude", "ja"): "exclude_ja",
    ("exclude", "en"): "exclude_en",
  }
  return mapping.get((bucket, language), "")
