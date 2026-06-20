"""Tests for manual claims evidence map skeleton builder (Phase 24.4A.3)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.validation.manual_claims_evidence_builder import (
  SKELETON_CAUTION_EN,
  SKELETON_CAUTION_JA,
  build_evidence_map_skeleton,
  build_query_plan_from_claim_elements,
  evidence_map_skeleton_exists,
  extract_claim_elements_from_text,
  full_evidence_map_exists,
  load_manual_claims,
  save_evidence_map_skeleton,
  split_claims_text,
)
from tech_cartography.validation.theme_validation import (
  ThemeValidationCase,
  run_existing_outputs_validation,
  save_user_manual_claims,
)

LONG_CLAIMS = """
【請求項1】
ポリアクリロニトリル（PAN）からなる炭素繊維前駆体であって、カルボキシル基を含み、
イタコン酸およびメタクリル酸を含む紡糸原液を凝固浴に通して得られる前駆体であり、
乾燥熱履歴が65℃以下であり、カルボン酸反応指数が700以下である前駆体。

【請求項2】
請求項1に記載の前駆体において、ボイドが緻密化され、毛羽が低減されていること。
""".strip()


def _save_claims(tmp_path: Path, pub: str = "JP2022090764A") -> Path:
  path, _warnings = save_user_manual_claims(
    publication_number=pub,
    claims_text=LONG_CLAIMS,
    output_dir=tmp_path,
  )
  assert path is not None
  return path


def test_load_manual_claims_json(tmp_path: Path) -> None:
  _save_claims(tmp_path)
  payload = load_manual_claims("JP2022090764A", tmp_path)
  assert "PAN" in payload["claims_text"]
  assert payload["_path"]


def test_split_claims_text_by_japanese_headers() -> None:
  claims = split_claims_text(LONG_CLAIMS)
  assert len(claims) >= 2
  assert claims[0]["claim_number"] == "1"
  assert "PAN" in claims[0]["claim_text"]


def test_extract_claim_elements_rule_based(tmp_path: Path) -> None:
  _save_claims(tmp_path)
  elements = extract_claim_elements_from_text("JP2022090764A", LONG_CLAIMS)
  assert elements
  first = elements[0]
  assert "PAN" in first.material_terms
  assert "rule-based extraction candidate" in first.caveat


def test_build_query_plan_from_claim_elements() -> None:
  elements = extract_claim_elements_from_text("JP2022090764A", LONG_CLAIMS)
  plans = build_query_plan_from_claim_elements(elements)
  assert plans
  assert plans[0]["must_have_terms"]


def test_save_evidence_map_skeleton_outputs(tmp_path: Path) -> None:
  claims_path = _save_claims(tmp_path)
  skeleton = build_evidence_map_skeleton("JP2022090764A", claims_path)
  paths = save_evidence_map_skeleton(skeleton, tmp_path)
  assert paths["evidence_map_skeleton_json"].exists()
  assert paths["claim_elements_csv"].exists()
  assert paths["query_plan_json"].exists()
  assert paths["evidence_gaps_md"].exists()
  assert paths["next_actions_md"].exists()
  md = paths["evidence_map_skeleton_md"].read_text(encoding="utf-8")
  assert SKELETON_CAUTION_EN in md
  assert SKELETON_CAUTION_JA in md
  data = json.loads(paths["evidence_map_skeleton_json"].read_text(encoding="utf-8"))
  assert data["publication_number"] == "JP2022090764A"
  assert data["publication_number"] != "US-12565719-B2"


def test_stage3_pass_when_skeleton_exists(tmp_path: Path) -> None:
  claims_path = _save_claims(tmp_path)
  skeleton = build_evidence_map_skeleton("JP2022090764A", claims_path)
  save_evidence_map_skeleton(skeleton, tmp_path)

  case = ThemeValidationCase(
    theme_id="pan_precursor_surface_internal_defects",
    theme_name="PAN",
    description="",
    core_keywords=["PAN"],
    application_keywords=[],
    material_or_process_keywords=[],
    exclude_keywords=[],
    seed_publication_numbers=["JP2022090764A"],
    validation_goal="",
  )
  result = run_existing_outputs_validation(case, tmp_path)
  statuses = {stage.stage: stage.status for stage in result.stages}
  assert statuses["fulltext_or_manual_claims_available"] == "pass"
  assert statuses["evidence_map_available_or_buildable"] == "pass"
  assert statuses["paper_candidates_available"] == "output_missing"


def test_full_evidence_map_vs_skeleton(tmp_path: Path) -> None:
  claims_path = _save_claims(tmp_path)
  skeleton = build_evidence_map_skeleton("JP2022090764A", claims_path)
  save_evidence_map_skeleton(skeleton, tmp_path)
  assert evidence_map_skeleton_exists(tmp_path, "JP2022090764A")
  assert not full_evidence_map_exists(tmp_path, "JP2022090764A")

  full_dir = tmp_path / "outputs" / "evidence_map_synthesis" / "JP2022090764A"
  (full_dir / "evidence_map_synthesis.json").write_text("{}", encoding="utf-8")
  assert full_evidence_map_exists(tmp_path, "JP2022090764A")


def test_ui_has_evidence_map_builder_section() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "Evidence Map生成準備 / Evidence Map Builder" in text
  assert "Claim Elementを抽出する" in text
  assert "Evidence Map skeletonを生成する" in text
  assert "外部APIは実行しません" in text
  assert "FTO" in text
