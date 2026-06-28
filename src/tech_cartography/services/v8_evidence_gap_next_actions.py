"""Evidence-aware Gap / Next Actions from Claim-Example binding (Phase 27S.6)."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from tech_cartography.runtime.v8_evidence_gap_schema import (
  BINDING_VERSION_EXPECTED,
  EVIDENCE_GAP_SAFETY_NOTICES,
  FORBIDDEN_GAP_WORDS,
  GAP_NEXT_ACTIONS_CSV_COLUMNS,
  GAP_SUMMARY_CSV_COLUMNS,
  GAP_TYPE_CLAIM_EXAMPLE_LINK,
  GAP_TYPE_NO_EXAMPLE_FACTS,
  GAP_TYPE_OCR_HUMAN_REVIEW,
  GAP_TYPE_PAPER_EVIDENCE,
  GAP_TYPE_PROCESS_CONDITION_REVIEW,
  GAP_TYPE_PROPERTY_VALUE_REVIEW,
  GAP_TYPE_READY_FOR_HUMAN_REVIEW,
  GAP_TYPE_STRUCTURE_PROPERTY_REVIEW,
  GAP_TYPE_TABLE_REVIEW,
  GENERATION_METHOD,
  EvidenceAwareGapRecord,
  EvidenceAwareGapReport,
  EvidenceAwareGapSummary,
  EvidenceAwareTopAction,
)
from tech_cartography.runtime.v8_research_theme_schema import normalize_publication_number
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_claim_example_binding import (
  find_latest_claim_example_links_dir,
  find_latest_example_facts_output,
)
from tech_cartography.services.v8_gap_next_actions_export import (
  LOCAL_V8_GAP_NEXT_ACTIONS_SUBDIR,
  get_v8_gap_next_actions_dir,
)

FACT_TYPE_PROPERTY = frozenset({"property_value", "property_candidate"})
FACT_TYPE_TABLE = frozenset({"table_candidate", "comparison_candidate"})
FACT_TYPE_PROCESS = frozenset({"process_condition"})
FACT_TYPE_STRUCTURE = frozenset({"structure_property", "structure_characterization"})

_PAPER_OUTPUT_HINTS = (
  "local_v8_paper",
  "paper_evidence",
  "paper_query_candidates",
  "evidence_map",
)


def _project_root(project_root: Path | str | None) -> Path:
  return Path(project_root) if project_root else Path.cwd()


def _parse_pipe_list(value: str | None) -> list[str]:
  if not value or str(value).strip().lower() in {"nan", "none", ""}:
    return []
  return [part.strip() for part in str(value).split("|") if part.strip()]


def _join_pipe(items: list[str]) -> str:
  return "|".join(items)


def _is_nonempty_field(value: str | None) -> bool:
  if value is None:
    return False
  text = str(value).strip()
  return bool(text) and text.lower() not in {"nan", "none", "[]"}


def _truthy(value: Any) -> bool:
  if isinstance(value, bool):
    return value
  text = str(value or "").strip().lower()
  return text in {"true", "1", "yes", "y"}


def _assert_safe_text(text: str) -> None:
  lowered = text.lower()
  for word in FORBIDDEN_GAP_WORDS:
    if word.lower() in lowered:
      raise ValueError(f"forbidden wording in gap output: {word}")


def _safe_join(parts: list[str]) -> str:
  text = " ".join(parts)
  _assert_safe_text(text)
  return text


def _gap_id(case_id: str, pub: str, claim_no: str, gap_type: str, index: int = 0) -> str:
  slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{case_id}_{pub}_{claim_no}_{gap_type}_{index}")
  return slug.strip("_")


def _action_priority_for(gap_type: str, support_level: str) -> str:
  if gap_type in {GAP_TYPE_READY_FOR_HUMAN_REVIEW, GAP_TYPE_OCR_HUMAN_REVIEW}:
    return "P1"
  if gap_type in {
    GAP_TYPE_PROPERTY_VALUE_REVIEW,
    GAP_TYPE_TABLE_REVIEW,
    GAP_TYPE_PROCESS_CONDITION_REVIEW,
    GAP_TYPE_STRUCTURE_PROPERTY_REVIEW,
    GAP_TYPE_PAPER_EVIDENCE,
  }:
    return "P2"
  return "P3"


def _severity_for(gap_type: str, support_level: str) -> str:
  if gap_type in {GAP_TYPE_READY_FOR_HUMAN_REVIEW, GAP_TYPE_OCR_HUMAN_REVIEW}:
    return "high_review_priority"
  if gap_type in {
    GAP_TYPE_PROPERTY_VALUE_REVIEW,
    GAP_TYPE_TABLE_REVIEW,
    GAP_TYPE_PROCESS_CONDITION_REVIEW,
    GAP_TYPE_STRUCTURE_PROPERTY_REVIEW,
  }:
    return "medium_review_priority"
  if gap_type in {GAP_TYPE_NO_EXAMPLE_FACTS, GAP_TYPE_CLAIM_EXAMPLE_LINK}:
    return "low_review_priority"
  return "info"


def _evidence_status_for(gap_type: str) -> str:
  mapping = {
    GAP_TYPE_NO_EXAMPLE_FACTS: "no_example_facts",
    GAP_TYPE_CLAIM_EXAMPLE_LINK: "candidate_found_needs_review",
    GAP_TYPE_OCR_HUMAN_REVIEW: "ocr_candidate_needs_review",
    GAP_TYPE_PROPERTY_VALUE_REVIEW: "property_candidate_needs_review",
    GAP_TYPE_TABLE_REVIEW: "table_candidate_needs_review",
    GAP_TYPE_READY_FOR_HUMAN_REVIEW: "ready_for_human_review",
  }
  return mapping.get(gap_type, "candidate_found_needs_review")


def _has_paper_outputs(project_root: Path) -> bool:
  outputs = project_root / "outputs"
  if not outputs.is_dir():
    return False
  for child in outputs.iterdir():
    if not child.is_dir():
      continue
    name = child.name.lower()
    if any(hint in name for hint in _PAPER_OUTPUT_HINTS):
      for pattern in ("*.csv", "*.json"):
        if list(child.glob(pattern)):
          return True
  return False


def load_claim_example_links_csv(path: Path) -> list[dict[str, str]]:
  with path.open(encoding="utf-8", newline="") as handle:
    return list(csv.DictReader(handle))


def load_binding_summary_csv(path: Path) -> list[dict[str, str]]:
  if not path.exists():
    return []
  with path.open(encoding="utf-8", newline="") as handle:
    return list(csv.DictReader(handle))


def _is_no_example_row(row: dict[str, str]) -> bool:
  support_type = str(row.get("support_type", "")).strip()
  support_level = str(row.get("support_level", "")).strip()
  warning = str(row.get("warning", "")).lower()
  if support_type == "no_example_support_candidate":
    return True
  if support_level == "none":
    return True
  if "no example facts" in warning:
    return True
  return False


def _has_link_evidence(row: dict[str, str]) -> bool:
  return _is_nonempty_field(row.get("linked_fact_ids")) or _is_nonempty_field(
    row.get("top_evidence_snippets"),
  )


def _build_gap_record(
  row: dict[str, str],
  *,
  gap_type: str,
  gap_label: str,
  gap_description: str,
  next_action: str,
  source_links_csv: str,
  index: int = 0,
) -> EvidenceAwareGapRecord:
  support_level = str(row.get("support_level", "")).strip()
  record = EvidenceAwareGapRecord(
    case_id=str(row.get("case_id", "")).strip(),
    publication_number=normalize_publication_number(str(row.get("publication_number", ""))),
    claim_no=str(row.get("claim_no", "")).strip(),
    gap_id=_gap_id(
      str(row.get("case_id", "")),
      str(row.get("publication_number", "")),
      str(row.get("claim_no", "")),
      gap_type,
      index,
    ),
    gap_type=gap_type,
    gap_severity=_severity_for(gap_type, support_level),
    gap_label=gap_label,
    gap_description=gap_description,
    next_action=next_action,
    action_owner="researcher",
    action_priority=_action_priority_for(gap_type, support_level),
    evidence_status=_evidence_status_for(gap_type),
    support_type=str(row.get("support_type", "")).strip(),
    support_level=support_level,
    matched_fact_types=str(row.get("matched_fact_types", "")).strip(),
    matched_elements=str(row.get("matched_elements", "")).strip(),
    missing_elements=str(row.get("missing_elements", "")).strip(),
    top_evidence_snippets=str(row.get("top_evidence_snippets", "")).strip(),
    linked_fact_ids=str(row.get("linked_fact_ids", "")).strip(),
    source_claim_example_links_csv=source_links_csv,
    source_example_facts_csv=str(row.get("source_example_facts_csv", "")).strip(),
    needs_human_review=_truthy(row.get("needs_human_review", True)),
    generation_method=GENERATION_METHOD,
    warning=str(row.get("warning", "")).strip(),
  )
  _assert_safe_text(
    f"{record.gap_label} {record.gap_description} {record.next_action}",
  )
  return record


def gaps_for_claim_link_row(
  row: dict[str, str],
  *,
  source_links_csv: str,
  paper_outputs_available: bool = False,
) -> list[EvidenceAwareGapRecord]:
  """Derive evidence-aware gaps for one claim-example binding row."""
  gaps: list[EvidenceAwareGapRecord] = []
  fact_types = set(_parse_pipe_list(row.get("matched_fact_types")))
  support_level = str(row.get("support_level", "")).strip()
  needs_review = _truthy(row.get("needs_human_review", True))
  has_evidence = _has_link_evidence(row)

  if _is_no_example_row(row):
    gaps.append(_build_gap_record(
      row,
      gap_type=GAP_TYPE_NO_EXAMPLE_FACTS,
      gap_label="実施例ファクト未取得",
      gap_description=(
        "この公報について実施例ファクトがまだ抽出されていない、または対応候補が未確認です。"
        " Claim-Example binding上も実施例裏取り候補が不足しています。"
      ),
      next_action=_safe_join([
        "公報PDFをアップロードし、OCRまたは本文抽出を実行してください。",
        "section抽出後、Gemini実施例ファクト抽出を実行してください。",
        "抽出後にClaim-Example bindingを再実行してください。",
      ]),
      source_links_csv=source_links_csv,
    ))
    return gaps

  if not has_evidence:
    gaps.append(_build_gap_record(
      row,
      gap_type=GAP_TYPE_CLAIM_EXAMPLE_LINK,
      gap_label="Claim-実施例対応候補未確認",
      gap_description=(
        "請求項に対応する実施例候補がまだ見つかっていません。"
        " linked_fact_ids / top_evidence_snippets が空です。"
      ),
      next_action=_safe_join([
        "Claim語彙と実施例語彙の対応を人手で確認してください。",
        "OCR本文・section切り出しを確認し、実施例番号・工程条件・物性候補を探してください。",
      ]),
      source_links_csv=source_links_csv,
    ))
    return gaps

  if support_level == "high_candidate" and has_evidence:
    gaps.append(_build_gap_record(
      row,
      gap_type=GAP_TYPE_READY_FOR_HUMAN_REVIEW,
      gap_label="人手レビュー可能な対応候補",
      gap_description=(
        "自動抽出としてはレビュー可能な対応候補があります。"
        " Evidenceは裏取り候補であり、証明ではありません。"
      ),
      next_action=_safe_join([
        "人手レビューへ回し、Export reportに含める候補として整理してください。",
        "top_evidence_snippetsとlinked_fact_idsを原文PDFと照合してください。",
      ]),
      source_links_csv=source_links_csv,
    ))

  if needs_review and has_evidence:
    gaps.append(_build_gap_record(
      row,
      gap_type=GAP_TYPE_OCR_HUMAN_REVIEW,
      gap_label="OCR由来の人手確認が必要",
      gap_description=(
        "OCR由来の可能性があるため、数値・単位・実施例番号の原文確認が必要です。"
        " 裏取り候補は取得済みですが、人手確認が必要です。"
      ),
      next_action=_safe_join([
        "PDF原文で該当箇所を確認してください。",
        "表の列・単位・実施例番号を確認し、OCR誤読を修正してください。",
      ]),
      source_links_csv=source_links_csv,
      index=1,
    ))

  if fact_types & FACT_TYPE_PROPERTY:
    gaps.append(_build_gap_record(
      row,
      gap_type=GAP_TYPE_PROPERTY_VALUE_REVIEW,
      gap_label="物性値候補の原文確認",
      gap_description=(
        "強度・弾性率などの物性値候補がありますが、原文確認が必要です。"
        " OCR由来の数値・単位は必ず人手確認してください。"
      ),
      next_action=_safe_join([
        "拉伸强度 / 拉伸模量 / GPa / MPa / 表1 を原文PDFで確認してください。",
        "property_valueの単位確認とproperty名の正規化を確認してください。",
      ]),
      source_links_csv=source_links_csv,
      index=2,
    ))

  if fact_types & FACT_TYPE_TABLE:
    gaps.append(_build_gap_record(
      row,
      gap_type=GAP_TYPE_TABLE_REVIEW,
      gap_label="表・比較表候補の原文確認",
      gap_description=(
        "表や比較表の候補がありますが、OCRで表構造が崩れている可能性があります。"
        " 原文確認が必要です。"
      ),
      next_action=_safe_join([
        "表1 / 性能对比表 / 比較対象 / 単位を原文PDFで確認してください。",
        "日本東レなど比較対象名と行列対応を人手確認してください。",
      ]),
      source_links_csv=source_links_csv,
      index=3,
    ))

  if fact_types & FACT_TYPE_PROCESS:
    gaps.append(_build_gap_record(
      row,
      gap_type=GAP_TYPE_PROCESS_CONDITION_REVIEW,
      gap_label="工程条件候補の原文確認",
      gap_description=(
        "工程条件候補がありますが、温度・時間・倍率・雰囲気の確認が必要です。"
      ),
      next_action=_safe_join([
        "预氧化 / 低温碳化 / 高温碳化 / 石墨化 の温度・時間・雰囲気・拉伸倍率を確認してください。",
      ]),
      source_links_csv=source_links_csv,
      index=4,
    ))

  if fact_types & FACT_TYPE_STRUCTURE:
    gaps.append(_build_gap_record(
      row,
      gap_type=GAP_TYPE_STRUCTURE_PROPERTY_REVIEW,
      gap_label="構造指標候補の原文確認",
      gap_description=(
        "取向角など構造指標候補がありますが、測定条件・意味の確認が必要です。"
      ),
      next_action=_safe_join([
        "取向角 / 微晶尺寸 / 配向関連指標の原文確認を行ってください。",
        "物性との関係を論文候補と照合してください（候補扱い）。",
      ]),
      source_links_csv=source_links_csv,
      index=5,
    ))

  if paper_outputs_available and has_evidence:
    gaps.append(_build_gap_record(
      row,
      gap_type=GAP_TYPE_PAPER_EVIDENCE,
      gap_label="論文Evidence候補の照合",
      gap_description=(
        "Claim-Example対応候補はありますが、論文Evidenceとの接続は未確認です。"
      ),
      next_action=_safe_join([
        "論文候補との対応を人手で確認してください。",
        "process-property / structure-property の文献照合を行ってください（候補扱い）。",
      ]),
      source_links_csv=source_links_csv,
      index=6,
    ))

  return gaps


def _summarize_publication(
  case_id: str,
  publication_number: str,
  claim_rows: list[dict[str, str]],
  gaps: list[EvidenceAwareGapRecord],
) -> EvidenceAwareGapSummary:
  pub_gaps = [g for g in gaps if g.publication_number == publication_number]
  claim_nos = {str(r.get("claim_no", "")).strip() for r in claim_rows}
  counts: dict[str, int] = defaultdict(int)
  for gap in pub_gaps:
    counts[gap.gap_type] += 1
    if gap.action_priority == "P1":
      counts["p1"] += 1
    elif gap.action_priority == "P2":
      counts["p2"] += 1
    else:
      counts["p3"] += 1

  warnings = [str(r.get("warning", "")).strip() for r in claim_rows if str(r.get("warning", "")).strip()]
  status = "ok" if pub_gaps else "no_gaps"
  if counts[GAP_TYPE_NO_EXAMPLE_FACTS] > 0:
    status = "no_example_facts"

  return EvidenceAwareGapSummary(
    case_id=case_id,
    publication_number=publication_number,
    claim_count=len(claim_nos),
    gap_count=len(pub_gaps),
    p1_action_count=counts["p1"],
    p2_action_count=counts["p2"],
    p3_action_count=counts["p3"],
    no_example_facts_gap_count=counts[GAP_TYPE_NO_EXAMPLE_FACTS],
    ocr_human_review_gap_count=counts[GAP_TYPE_OCR_HUMAN_REVIEW],
    property_value_review_gap_count=counts[GAP_TYPE_PROPERTY_VALUE_REVIEW],
    table_review_gap_count=counts[GAP_TYPE_TABLE_REVIEW],
    process_condition_review_gap_count=counts[GAP_TYPE_PROCESS_CONDITION_REVIEW],
    structure_property_review_gap_count=counts[GAP_TYPE_STRUCTURE_PROPERTY_REVIEW],
    ready_for_human_review_count=counts[GAP_TYPE_READY_FOR_HUMAN_REVIEW],
    needs_human_review=True,
    status=status,
    warning="; ".join(dict.fromkeys(warnings)),
  )


def build_evidence_aware_gap_report(
  case_id: str,
  *,
  project_root: Path | str | None = None,
  claim_example_links_dir: Path | str | None = None,
) -> EvidenceAwareGapReport:
  root = _project_root(project_root)
  bind_dir = Path(claim_example_links_dir) if claim_example_links_dir else find_latest_claim_example_links_dir(case_id, root)
  report = EvidenceAwareGapReport(case_id=case_id)

  if bind_dir is None or not bind_dir.is_dir():
    report.warnings.append("claim_example_links.csv が見つかりません — 先に Claim-Example binding を実行してください。")
    return report

  links_csv = bind_dir / "claim_example_links.csv"
  summary_csv = bind_dir / "claim_example_binding_summary.csv"
  if not links_csv.exists():
    report.warnings.append(f"claim_example_links.csv missing: {links_csv}")
    return report

  report.source_claim_example_links_dir = str(bind_dir)
  report.source_claim_example_links_csv = str(links_csv)
  report.source_binding_summary_csv = str(summary_csv) if summary_csv.exists() else ""

  facts_dir = find_latest_example_facts_output(case_id, root / "outputs")
  if facts_dir:
    report.source_example_facts_csv = str(facts_dir / "example_facts.csv")

  link_rows = load_claim_example_links_csv(links_csv)
  if not link_rows:
    report.warnings.append("claim_example_links.csv is empty")
    return report

  binding_versions = {str(r.get("binding_version", "")).strip() for r in link_rows}
  binding_versions.discard("")
  if binding_versions:
    report.binding_version = sorted(binding_versions)[-1]
    if BINDING_VERSION_EXPECTED not in binding_versions:
      report.warnings.append(
        f"binding_version={report.binding_version} — phase27s54 が望ましいです。",
      )

  paper_available = _has_paper_outputs(root)
  all_gaps: list[EvidenceAwareGapRecord] = []
  for row in link_rows:
    if str(row.get("case_id", case_id)).strip() != case_id:
      row = {**row, "case_id": case_id}
    row_gaps = gaps_for_claim_link_row(
      row,
      source_links_csv=str(links_csv),
      paper_outputs_available=paper_available,
    )
    all_gaps.extend(row_gaps)

  report.gaps = all_gaps

  pubs: dict[str, list[dict[str, str]]] = defaultdict(list)
  for row in link_rows:
    pub = normalize_publication_number(str(row.get("publication_number", "")))
    pubs[pub].append(row)

  for pub, rows in sorted(pubs.items()):
    report.summaries.append(_summarize_publication(case_id, pub, rows, all_gaps))

  return report


def gaps_to_markdown(report: EvidenceAwareGapReport) -> str:
  lines = [
    f"# Evidence-aware Gap / Next Actions — {report.case_id}",
    "",
    f"- generated_at: {report.generated_at}",
    f"- generation_method: {report.generation_method}",
    f"- binding_version: {report.binding_version or '(unknown)'}",
    f"- gap_count: {report.gap_count}",
    "",
    "## Safety",
  ]
  for notice in EVIDENCE_GAP_SAFETY_NOTICES:
    lines.append(f"- {notice}")
  lines.extend([
    "",
    "## Gap records",
    "",
    "| publication | claim | gap_type | priority | evidence_status | label |",
    "| --- | --- | --- | --- | --- | --- |",
  ])
  for gap in report.gaps[:100]:
    lines.append(
      f"| {gap.publication_number} | {gap.claim_no} | {gap.gap_type} | "
      f"{gap.action_priority} | {gap.evidence_status} | {gap.gap_label} |",
    )
  lines.extend(["", "## Sources", f"- {report.source_claim_example_links_csv}"])
  if report.source_example_facts_csv:
    lines.append(f"- {report.source_example_facts_csv}")
  if report.warnings:
    lines.extend(["", "## Warnings", *[f"- {w}" for w in report.warnings]])
  return "\n".join(lines)


def summary_to_markdown(report: EvidenceAwareGapReport) -> str:
  lines = [
    f"# Gap / Next Actions Summary — {report.case_id}",
    "",
    "| publication | gaps | ready | ocr | property | table | process | structure | no_facts |",
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
  ]
  for summary in report.summaries:
    lines.append(
      f"| {summary.publication_number} | {summary.gap_count} | "
      f"{summary.ready_for_human_review_count} | {summary.ocr_human_review_gap_count} | "
      f"{summary.property_value_review_gap_count} | {summary.table_review_gap_count} | "
      f"{summary.process_condition_review_gap_count} | {summary.structure_property_review_gap_count} | "
      f"{summary.no_example_facts_gap_count} |",
    )
  return "\n".join(lines)


def load_evidence_gap_summary_by_pub(
  case_id: str,
  project_root: Path | str | None = None,
) -> dict[str, dict[str, str]]:
  gap_dir = find_latest_evidence_aware_gap_dir(case_id, project_root)
  if not gap_dir or not is_evidence_aware_gap_pack(gap_dir):
    return {}
  summary_csv = gap_dir / "gap_next_actions_summary.csv"
  if not summary_csv.exists():
    return {}
  with summary_csv.open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
  return {
    normalize_publication_number(str(row.get("publication_number", ""))): row
    for row in rows
    if str(row.get("publication_number", "")).strip()
  }


def evidence_aware_gap_primary_available(
  case_id: str,
  project_root: Path | str | None = None,
) -> bool:
  gap_dir = find_latest_evidence_aware_gap_dir(case_id, project_root)
  if gap_dir is None or not is_evidence_aware_gap_pack(gap_dir):
    return False
  csv_path = gap_dir / "gap_next_actions.csv"
  return csv_path.exists() and csv_path.stat().st_size > 0


def _dedupe_evidence_snippets(
  gaps: list[EvidenceAwareGapRecord],
) -> list[tuple[str, str, str]]:
  seen: set[tuple[str, str, str]] = set()
  items: list[tuple[str, str, str]] = []
  for gap in gaps:
    for snippet in _parse_pipe_list(gap.top_evidence_snippets):
      key = (gap.publication_number, str(gap.claim_no), snippet.strip())
      if key in seen or not snippet.strip():
        continue
      seen.add(key)
      items.append(key)
  return items


def build_top3_next_actions_from_evidence_gaps(
  report: EvidenceAwareGapReport,
) -> list[EvidenceAwareTopAction]:
  actions: list[EvidenceAwareTopAction] = []
  summaries = sorted(
    report.summaries,
    key=lambda s: (-s.ready_for_human_review_count, s.publication_number),
  )
  review_ready = [s for s in summaries if s.ready_for_human_review_count > 0]

  if review_ready:
    pub = review_ready[0].publication_number
    pub_gaps = [g for g in report.gaps if g.publication_number == pub]
    prop_table = [
      g for g in pub_gaps
      if g.gap_type in {GAP_TYPE_PROPERTY_VALUE_REVIEW, GAP_TYPE_TABLE_REVIEW}
    ]
    if prop_table:
      claims = sorted({g.claim_no for g in prop_table}, key=lambda x: (len(x), x))
      claim_label = "/".join(claims[:8])
      if len(claims) > 8:
        claim_label += f" 他{len(claims) - 8}件"
      actions.append(EvidenceAwareTopAction(
        action_rank=len(actions) + 1,
        action_type="review_property_table_candidates",
        action_title=f"{pub} claim {claim_label} の物性値・表候補を原文PDFで確認",
        action_description=(
          "property_value / table_candidate の裏取り候補について、"
          "拉伸强度・拉伸模量・表1・単位を原文PDFで確認してください（候補扱い）。"
        ),
        target_publication_number=pub,
        target_claim_no=claims[0] if claims else "",
        expected_output="拉伸强度・拉伸模量・表1・単位の確認結果（候補メモ）",
        priority_reason="review-ready candidate with property/table evidence snippets",
        watch_profile_update_hint=f"Watch: {pub} property/table review tasks for claims {claim_label}",
        email_digest_hint=f"Digest: {pub} property/table candidates pending source PDF review",
        scheduler_followup_hint="Scheduler: queue human review for property/table candidates",
      ))

    process_gaps = [g for g in pub_gaps if g.gap_type == GAP_TYPE_PROCESS_CONDITION_REVIEW]
    if process_gaps and len(actions) < 3:
      claims = sorted({g.claim_no for g in process_gaps}, key=lambda x: (len(x), x))
      claim_label = "〜".join([claims[0], claims[-1]]) if len(claims) > 1 else claims[0]
      actions.append(EvidenceAwareTopAction(
        action_rank=len(actions) + 1,
        action_type="review_process_conditions",
        action_title=f"{pub} claim {claim_label} の工程条件候補を原文PDFで確認",
        action_description=(
          "预氧化 / 低温碳化 / 高温碳化 / 石墨化 の温度・時間・拉伸倍率を"
          "原文PDFで確認してください（OCR由来の可能性あり）。"
        ),
        target_publication_number=pub,
        target_claim_no=claims[0] if claims else "",
        expected_output="工程条件候補の温度・時間・雰囲気・拉伸倍率の確認結果",
        priority_reason="process_condition review gaps from claim-example binding",
        watch_profile_update_hint=f"Watch: {pub} process condition review for claims {claim_label}",
        email_digest_hint=f"Digest: {pub} process condition candidates pending review",
        scheduler_followup_hint="Scheduler: queue process condition human review",
      ))

  no_fact_pubs = sorted(
    s.publication_number for s in report.summaries if s.no_example_facts_gap_count > 0
  )
  if no_fact_pubs and len(actions) < 3:
    pub_list = " / ".join(no_fact_pubs)
    actions.append(EvidenceAwareTopAction(
      action_rank=len(actions) + 1,
      action_type="complete_example_fact_pipeline",
      action_title="他Top5公報のOCR / section / example facts抽出を進める",
      action_description=(
        f"実施例ファクト未取得の公報（{pub_list}）について、"
        "PDF/OCR/section/Gemini facts/claim-example binding を順に実行してください。"
      ),
      target_publication_number=no_fact_pubs[0],
      target_claim_no="",
      expected_output="実施例ファクト抽出とclaim-example対応候補（候補扱い）",
      priority_reason="publications without example facts remain in pipeline",
      watch_profile_update_hint=f"Watch: prioritize example fact pipeline for {pub_list}",
      email_digest_hint=f"Digest: {len(no_fact_pubs)} publications still lack example facts",
      scheduler_followup_hint="Scheduler: track incomplete Top5 PDF pipelines",
    ))

  while len(actions) < 3:
    ocr_gaps = [g for g in report.gaps if g.gap_type == GAP_TYPE_OCR_HUMAN_REVIEW]
    if ocr_gaps and not any(a.action_type == "review_ocr_evidence" for a in actions):
      gap = ocr_gaps[0]
      actions.append(EvidenceAwareTopAction(
        action_rank=len(actions) + 1,
        action_type="review_ocr_evidence",
        action_title=f"{gap.publication_number} claim {gap.claim_no} のOCR由来根拠候補を原文確認",
        action_description=gap.gap_description,
        target_publication_number=gap.publication_number,
        target_claim_no=gap.claim_no,
        expected_output="OCR由来数値・単位・実施例番号の原文確認結果",
        priority_reason="OCR-derived evidence requires source PDF review",
        watch_profile_update_hint=f"Watch: OCR review for {gap.publication_number}",
        email_digest_hint=f"Digest: OCR review pending for {gap.publication_number}",
      ))
      continue
    break

  for idx, action in enumerate(actions[:3], start=1):
    action.action_rank = idx
  text_blob = " ".join(
    f"{a.action_title} {a.action_description}" for a in actions[:3]
  )
  _assert_safe_text(text_blob)
  return actions[:3]


def build_watch_profile_proposal_md(report: EvidenceAwareGapReport) -> str:
  top3 = build_top3_next_actions_from_evidence_gaps(report)
  lines = [
    f"# Watch Profile Update Proposal — {report.case_id}",
    "",
    "Evidence-aware Gap（claim-example binding由来）に基づく定点観測候補です。",
    "候補情報のみ — 人手承認後に Watch Profile へ反映してください。",
    "",
  ]
  for action in top3:
    lines.append(f"- {action.watch_profile_update_hint or action.action_title}")
  ready_pubs = [s.publication_number for s in report.summaries if s.ready_for_human_review_count > 0]
  if ready_pubs:
    lines.append(f"- Review-ready publications: {', '.join(ready_pubs)}")
  no_fact = [s.publication_number for s in report.summaries if s.no_example_facts_gap_count > 0]
  if no_fact:
    lines.append(f"- Publications needing example fact pipeline: {', '.join(no_fact)}")
  return "\n".join(lines)


def build_digest_summary_md(report: EvidenceAwareGapReport) -> str:
  top3 = build_top3_next_actions_from_evidence_gaps(report)
  lines = [
    f"# Digest Summary — {report.case_id}",
    "",
    "Evidence-aware Gap digest preview（送信は行いません — preview only）。",
    "",
    "## Top 3 Next Actions",
  ]
  for action in top3:
    lines.append(
      f"{action.action_rank}. **{action.action_title}** ({action.action_type}) — "
      f"{action.target_publication_number}"
    )
    lines.append(f"   - expected_output: {action.expected_output}")
    if action.email_digest_hint:
      lines.append(f"   - digest_hint: {action.email_digest_hint}")
  lines.extend([
    "",
    "## Summary counts",
  ])
  for summary in report.summaries:
    lines.append(
      f"- {summary.publication_number}: gaps={summary.gap_count}, "
      f"ready={summary.ready_for_human_review_count}, "
      f"no_facts={summary.no_example_facts_gap_count}",
    )
  return "\n".join(lines)


def human_review_checklist_markdown(report: EvidenceAwareGapReport) -> str:
  lines = [
    f"# Human Review Checklist — {report.case_id}",
    "",
    "Gapは弱点ではなく未確認事項です。Evidenceは裏取り候補であり、証明ではありません。",
    "",
  ]

  ready_pubs = sorted(
    s.publication_number for s in report.summaries if s.ready_for_human_review_count > 0
  )
  if ready_pubs:
    lines.extend(["## Review-ready publication", "", *[f"- {pub}" for pub in ready_pubs], ""])

  for pub in ready_pubs:
    pub_gaps = [g for g in report.gaps if g.publication_number == pub]
    claims = sorted({g.claim_no for g in pub_gaps}, key=lambda x: (len(x), x))
    if claims:
      lines.extend([f"## {pub}", "", "### Claims to review", "", f"- claim {', '.join(claims)}", ""])

  deduped = _dedupe_evidence_snippets(report.gaps)
  if deduped:
    lines.extend(["### 見るべき根拠候補（重複除去）", ""])
    for pub, claim_no, snippet in deduped[:30]:
      lines.append(f"- {pub} claim {claim_no}: {snippet[:200]}")
    lines.append("")

  prop_gaps = [g for g in report.gaps if g.gap_type == GAP_TYPE_PROPERTY_VALUE_REVIEW]
  table_gaps = [g for g in report.gaps if g.gap_type == GAP_TYPE_TABLE_REVIEW]
  if prop_gaps or table_gaps:
    lines.extend(["### Property / table items to verify", ""])
    for gap in prop_gaps + table_gaps:
      snippets = _parse_pipe_list(gap.top_evidence_snippets)
      hint = " / ".join(snippets[:2]) if snippets else gap.gap_label
      lines.append(f"- claim {gap.claim_no}: {hint}")
    lines.append("")

  proc_gaps = [g for g in report.gaps if g.gap_type == GAP_TYPE_PROCESS_CONDITION_REVIEW]
  if proc_gaps:
    claims = sorted({g.claim_no for g in proc_gaps}, key=lambda x: (len(x), x))
    lines.extend([
      "### Process condition items to verify",
      "",
      f"- claim {', '.join(claims)}: 预氧化 / 低温碳化 / 高温碳化 / 石墨化",
      "",
    ])

  struct_gaps = [g for g in report.gaps if g.gap_type == GAP_TYPE_STRUCTURE_PROPERTY_REVIEW]
  if struct_gaps:
    lines.extend(["### Structure items to verify", "", "- orientation_angle / 取向角（候補）", ""])

  no_fact_summaries = [s for s in report.summaries if s.no_example_facts_gap_count > 0]
  if no_fact_summaries:
    lines.extend(["### Publications requiring next extraction", ""])
    for summary in no_fact_summaries:
      pub = summary.publication_number
      note = "example facts pending"
      if summary.status == "no_example_facts":
        note = "OCR or facts extraction pending"
      lines.append(f"- {pub}: {note}")
    lines.append("")

  return "\n".join(lines)


def find_latest_evidence_aware_gap_dir(
  case_id: str | None = None,
  project_root: Path | str | None = None,
) -> Path | None:
  base = get_v8_gap_next_actions_dir(project_root)
  if not base.is_dir():
    return None
  candidates = []
  for pack in base.iterdir():
    if not pack.is_dir():
      continue
    if case_id and not pack.name.startswith(f"{case_id}_"):
      continue
    manifest = pack / "evidence_gap_manifest.json"
    summary = pack / "gap_next_actions_summary.csv"
    if manifest.exists() or summary.exists():
      candidates.append(pack)
  if not candidates:
    return None
  return max(candidates, key=lambda p: p.stat().st_mtime)


def is_evidence_aware_gap_pack(pack_dir: Path) -> bool:
  manifest = pack_dir / "evidence_gap_manifest.json"
  if manifest.exists():
    try:
      data = json.loads(manifest.read_text(encoding="utf-8"))
      return data.get("generation_method") == GENERATION_METHOD
    except json.JSONDecodeError:
      return False
  csv_path = pack_dir / "gap_next_actions.csv"
  if not csv_path.exists():
    return False
  with csv_path.open(encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle)
    if not reader.fieldnames:
      return False
    return "generation_method" in reader.fieldnames and "gap_severity" in reader.fieldnames


def export_evidence_aware_gap_next_actions(
  report: EvidenceAwareGapReport,
  *,
  project_root: Path | str | None = None,
) -> Path:
  root = _project_root(project_root)
  stamp = report.generated_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
  digest = hashlib.sha256(
    f"{report.case_id}|evidence_gap|{stamp}|{report.gap_count}".encode(),
  ).hexdigest()[:8]
  out_dir = get_v8_gap_next_actions_dir(root) / f"{report.case_id}_{stamp}_{digest}"
  out_dir.mkdir(parents=True, exist_ok=True)

  csv_path = out_dir / "gap_next_actions.csv"
  md_path = out_dir / "gap_next_actions.md"
  summary_csv_path = out_dir / "gap_next_actions_summary.csv"
  summary_md_path = out_dir / "gap_next_actions_summary.md"
  checklist_path = out_dir / "human_review_checklist.md"
  manifest_path = out_dir / "evidence_gap_manifest.json"

  with csv_path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(GAP_NEXT_ACTIONS_CSV_COLUMNS))
    writer.writeheader()
    for gap in report.gaps:
      writer.writerow(gap.to_dict())

  md_path.write_text(gaps_to_markdown(report), encoding="utf-8")

  with summary_csv_path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(GAP_SUMMARY_CSV_COLUMNS))
    writer.writeheader()
    for summary in report.summaries:
      writer.writerow(summary.to_dict())

  summary_md_path.write_text(summary_to_markdown(report), encoding="utf-8")
  checklist_path.write_text(human_review_checklist_markdown(report), encoding="utf-8")
  watch_path = out_dir / "watch_profile_update_proposal.md"
  digest_path = out_dir / "digest_summary.md"
  watch_path.write_text(build_watch_profile_proposal_md(report), encoding="utf-8")
  digest_path.write_text(build_digest_summary_md(report), encoding="utf-8")

  manifest = {
    "case_id": report.case_id,
    "generated_at": report.generated_at,
    "generation_method": GENERATION_METHOD,
    "binding_version": report.binding_version,
    "gap_count": report.gap_count,
    "source_claim_example_links_dir": report.source_claim_example_links_dir,
    "files": {
      "gap_next_actions_csv": str(csv_path),
      "gap_next_actions_md": str(md_path),
      "gap_next_actions_summary_csv": str(summary_csv_path),
      "gap_next_actions_summary_md": str(summary_md_path),
      "human_review_checklist_md": str(checklist_path),
      "watch_profile_update_proposal_md": str(watch_path),
      "digest_summary_md": str(digest_path),
    },
    "safety_notices": list(EVIDENCE_GAP_SAFETY_NOTICES),
    "warnings": report.warnings,
  }
  manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
  return out_dir


def build_and_export_evidence_aware_gap_next_actions(
  case_id: str,
  *,
  project_root: Path | str | None = None,
) -> tuple[EvidenceAwareGapReport, Path]:
  report = build_evidence_aware_gap_report(case_id, project_root=project_root)
  out_dir = export_evidence_aware_gap_next_actions(report, project_root=project_root)
  return report, out_dir
