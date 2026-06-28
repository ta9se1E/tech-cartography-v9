"""Tests for Phase27S.7 demo flow / Weekly Watch / Export readiness."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tech_cartography.runtime.v8_demo_flow_export_schema import (
  DEMO_FLOW_SAFETY_NOTICES,
  READINESS_STATUS_DEMO_OFF,
  READINESS_STATUS_READY,
  READINESS_STATUS_REMAINING,
  SUBMISSION_DEMO_PUB,
)
from tech_cartography.runtime.v8_top5_pdf_pipeline_status_schema import Top5PdfPipelineStatus
from tech_cartography.services.v8_demo_flow_export_readiness import (
  build_submission_demo_readiness,
  export_demo_flow_bundle,
  find_latest_demo_export_bundle_dir,
  load_evidence_aware_watch_context,
)
from tech_cartography.ui.v8_judge_mode_copy import JUDGE_NEXT_TAB, TAB_DO_NEXT

CASE_ID = "test_case_demo_flow_s7"
PUB_CN108 = "CN108286090A"
PUB_OTHER = "CN105401262A"

FORBIDDEN_DEMO_PHRASES = (
  "OCR完了で裏取り完了",
  "証明済み",
  "権利範囲を支える",
  "PDF自動ダウンロード済み",
  "侵害判断",
  "FTO判断",
  "有効性判断",
  "無効理由",
  "支えています",
  "証明しています",
  "裏取り完了",
  "次PhaseでGapロジック更新",
)

PHASE27S7_SOURCE_FILES = (
  "src/tech_cartography/runtime/v8_demo_flow_export_schema.py",
  "src/tech_cartography/services/v8_demo_flow_export_readiness.py",
  "src/tech_cartography/ui/v8_evidence_aware_watch_ui.py",
  "src/tech_cartography/ui/v8_submission_demo_readiness_ui.py",
)


def _cn108_pipeline_status(**overrides: object) -> Top5PdfPipelineStatus:
  defaults: dict[str, object] = {
    "case_id": CASE_ID,
    "publication_number": PUB_CN108,
    "pdf_uploaded": True,
    "pdf_text_extracted": True,
    "vision_ocr_text_extracted": True,
    "sections_extracted": True,
    "has_examples": True,
    "examples_count": 2,
    "example_facts_extracted": True,
    "claim_example_links_generated": True,
    "evidence_aware_gaps_generated": True,
    "evidence_ready_for_review": True,
  }
  defaults.update(overrides)
  return Top5PdfPipelineStatus(**defaults)  # type: ignore[arg-type]


def _other_pub_pipeline_status(**overrides: object) -> Top5PdfPipelineStatus:
  defaults: dict[str, object] = {
    "case_id": CASE_ID,
    "publication_number": PUB_OTHER,
    "pdf_uploaded": False,
    "next_action": "PDFを取得してアップロード",
  }
  defaults.update(overrides)
  return Top5PdfPipelineStatus(**defaults)  # type: ignore[arg-type]


def _seed_case_artifacts(tmp_path: Path) -> tuple[Path, Path]:
  case_dir = tmp_path / "cases" / CASE_ID
  case_dir.mkdir(parents=True)
  claims_path = case_dir / "claims_input.csv"
  with claims_path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(
      handle,
      fieldnames=["case_id", "publication_number", "claim_no", "claim_text", "status"],
    )
    writer.writeheader()
    writer.writerow({
      "case_id": CASE_ID,
      "publication_number": PUB_CN108,
      "claim_no": "1",
      "claim_text": "sample claim",
      "status": "loaded",
    })

  shortlist_dir = tmp_path / "outputs" / "local_v8_patent_shortlists" / f"{CASE_ID}_t_short"
  shortlist_dir.mkdir(parents=True)
  (shortlist_dir / "patent_shortlist_top5.csv").write_text("publication_number\nCN108286090A\n", encoding="utf-8")

  bind_dir = tmp_path / "outputs" / "local_v8_claim_example_links" / f"{CASE_ID}_t_bind"
  bind_dir.mkdir(parents=True)
  (bind_dir / "claim_example_binding_summary.csv").write_text("case_id,publication_number\n", encoding="utf-8")
  links = bind_dir / "claim_example_links.csv"
  with links.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(
      handle,
      fieldnames=[
        "case_id", "publication_number", "claim_no", "support_type", "support_level",
        "matched_fact_types", "linked_fact_ids", "top_evidence_snippets", "needs_human_review",
        "binding_version", "gap_label", "gap_description", "next_action",
      ],
    )
    writer.writeheader()
    writer.writerow({
      "case_id": CASE_ID,
      "publication_number": PUB_CN108,
      "claim_no": "1",
      "support_type": "mixed_support_candidate",
      "support_level": "high_candidate",
      "matched_fact_types": "property_value|table_candidate",
      "linked_fact_ids": "f1",
      "top_evidence_snippets": "拉伸强度 4.38GPa",
      "needs_human_review": "True",
      "binding_version": "phase27s54",
      "gap_label": "x",
      "gap_description": "x",
      "next_action": "x",
    })

  gap_dir = tmp_path / "outputs" / "local_v8_gap_next_actions" / f"{CASE_ID}_t_gap"
  gap_dir.mkdir(parents=True)
  (gap_dir / "evidence_gap_manifest.json").write_text(
    json.dumps({"generation_method": "claim_example_evidence_phase27s6"}),
    encoding="utf-8",
  )
  (gap_dir / "gap_next_actions.csv").write_text(
    "generation_method,gap_severity,publication_number,claim_no\n"
    "claim_example_evidence_phase27s6,review_needed,CN108286090A,1\n",
    encoding="utf-8",
  )
  (gap_dir / "watch_profile_update_proposal.md").write_text(
    "# Watch Profile update proposal\n\n"
    "- CN108286090Aの物性値・表候補の原文確認\n"
    "- CN108286090Aの工程条件確認\n"
    f"- {PUB_OTHER}のOCR / section / facts抽出\n",
    encoding="utf-8",
  )
  (gap_dir / "digest_summary.md").write_text(
    "# Digest preview\n\n"
    "## 件名案\n"
    f"[Digest preview] {CASE_ID}\n\n"
    "## Review-ready claims\n"
    "- CN108286090A claim 1\n",
    encoding="utf-8",
  )
  (gap_dir / "human_review_checklist.md").write_text("# Human review checklist\n", encoding="utf-8")
  return bind_dir, gap_dir


def test_watch_context_loads_proposal_and_digest(tmp_path: Path):
  _seed_case_artifacts(tmp_path)
  ctx = load_evidence_aware_watch_context(CASE_ID, project_root=tmp_path)
  assert ctx is not None
  assert ctx.watch_profile_path.endswith("watch_profile_update_proposal.md")
  assert ctx.digest_summary_path.endswith("digest_summary.md")
  assert "Watch Profile update proposal" in ctx.watch_profile_text
  assert "Digest preview" in ctx.digest_preview_text
  assert ctx.watch_proposal_bullets
  assert "物性値" in ctx.watch_proposal_bullets[0]


def test_judge_mode_email_and_scheduler_are_normal_off(tmp_path: Path):
  _seed_case_artifacts(tmp_path)
  ctx = load_evidence_aware_watch_context(CASE_ID, project_root=tmp_path)
  assert ctx is not None
  assert ctx.email_sent is False
  assert ctx.scheduler_started is False
  assert ctx.demo_mode is True

  items = build_submission_demo_readiness(CASE_ID, project_root=tmp_path)
  email_item = next(i for i in items if i.label == "Email sending")
  sched_item = next(i for i in items if i.label == "Scheduler")
  assert email_item.status == READINESS_STATUS_DEMO_OFF
  assert sched_item.status == READINESS_STATUS_DEMO_OFF


@patch("tech_cartography.services.v8_demo_flow_export_readiness.build_top5_pdf_pipeline_status")
def test_cn108_readiness_ready_other_top5_remaining(mock_pipeline, tmp_path: Path):
  _seed_case_artifacts(tmp_path)
  mock_pipeline.return_value = [
    _cn108_pipeline_status(),
    _other_pub_pipeline_status(),
  ]
  items = build_submission_demo_readiness(CASE_ID, project_root=tmp_path)
  by_label = {i.label: i for i in items}
  assert by_label[f"{SUBMISSION_DEMO_PUB} OCR"].status == READINESS_STATUS_READY
  assert by_label[f"{SUBMISSION_DEMO_PUB} example facts"].status == READINESS_STATUS_READY
  assert by_label["Claim-example evidence detail"].status == READINESS_STATUS_READY
  assert by_label["Evidence-aware Gap"].status == READINESS_STATUS_READY
  assert by_label["Weekly Watch preview"].status == READINESS_STATUS_READY
  assert by_label["Email sending"].status != READINESS_STATUS_REMAINING
  assert by_label["Scheduler"].status != READINESS_STATUS_REMAINING
  assert by_label["Export bundle"].status == READINESS_STATUS_REMAINING


def test_export_bundle_references_latest_gap_artifacts(tmp_path: Path):
  bind_dir, gap_dir = _seed_case_artifacts(tmp_path)
  result = export_demo_flow_bundle(CASE_ID, project_root=tmp_path)
  out = Path(result.output_dir)
  assert out.is_dir()
  assert (out / "latest_gap_next_actions.csv").exists()
  assert (out / "latest_claim_example_links.csv").exists()
  assert (out / "human_review_checklist.md").exists()
  assert (out / "watch_profile_update_proposal.md").exists()
  assert (out / "digest_summary.md").exists()
  assert (out / "demo_summary.md").exists()
  assert (out / "demo_artifact_trace.md").exists()
  manifest = json.loads((out / "demo_export_manifest.json").read_text(encoding="utf-8"))
  assert manifest["email_sent"] is False
  assert manifest["scheduler_started"] is False
  assert str(gap_dir) in manifest["source_paths"]["evidence_aware_gap_dir"]
  assert str(bind_dir) in manifest["source_paths"]["claim_example_links_dir"]
  assert find_latest_demo_export_bundle_dir(CASE_ID, tmp_path) == out


def test_demo_readiness_ready_after_export_bundle(tmp_path: Path):
  _seed_case_artifacts(tmp_path)
  with patch(
    "tech_cartography.services.v8_demo_flow_export_readiness.build_top5_pdf_pipeline_status",
    return_value=[_cn108_pipeline_status(), _other_pub_pipeline_status()],
  ):
    export_demo_flow_bundle(CASE_ID, project_root=tmp_path)
    items = build_submission_demo_readiness(CASE_ID, project_root=tmp_path)
  by_label = {i.label: i for i in items}
  assert by_label["Export bundle"].status == READINESS_STATUS_READY


def test_judge_next_tab_order_unchanged():
  chain = [
    ("intro", "input"),
    ("input", "sources"),
    ("sources", "patent_shortlist"),
    ("patent_shortlist", "claim_map"),
    ("claim_map", "evidence_map"),
    ("evidence_map", "gap_next_actions"),
    ("gap_next_actions", "fixed_point_observation"),
    ("fixed_point_observation", "export"),
  ]
  for current, nxt in chain:
    assert JUDGE_NEXT_TAB[current] == nxt
  assert "Weekly Watch" in TAB_DO_NEXT["gap_next_actions"]
  assert "Demo Export Bundle" in TAB_DO_NEXT["fixed_point_observation"]
  assert "提出デモ完了" in TAB_DO_NEXT["export"]


def test_phase27s7_modules_avoid_forbidden_phrases():
  blob = "\n".join(
    Path(path).read_text(encoding="utf-8")
    for path in PHASE27S7_SOURCE_FILES
  )
  for phrase in FORBIDDEN_DEMO_PHRASES:
    for line in blob.splitlines():
      if phrase not in line:
        continue
      if any(token in line for token in ("行いません", "ではありません", "ではない", "not sent")):
        continue
      assert False, f"forbidden phrase found: {phrase} -> {line.strip()!r}"


def test_safety_notices_use_allowed_framing():
  joined = " ".join(DEMO_FLOW_SAFETY_NOTICES)
  assert "裏取り候補" in joined
  assert "未確認事項" in joined
  assert "demo mode" in joined.lower() or "not sent" in joined.lower()


def test_export_does_not_invoke_external_services(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
  _seed_case_artifacts(tmp_path)

  def _boom(*_args, **_kwargs):
    raise AssertionError("external API must not be called in demo export")

  monkeypatch.setattr(
    "tech_cartography.services.v8_demo_flow_export_readiness.build_top5_pdf_pipeline_status",
    lambda *_a, **_k: [_cn108_pipeline_status()],
  )
  for target in (
    "requests.get",
    "requests.post",
    "smtplib.SMTP",
  ):
    try:
      monkeypatch.setattr(target, _boom)
    except Exception:
      pass

  result = export_demo_flow_bundle(CASE_ID, project_root=tmp_path)
  assert result.files
