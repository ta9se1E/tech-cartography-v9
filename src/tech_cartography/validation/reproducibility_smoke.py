"""Reproducibility smoke run — diagnose Evidence Map pipeline progress per patent (Phase 22)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from tech_cartography.evidence.claims_based_paper_query_builder import (
  build_claims_paper_query_plan,
  save_claims_paper_query_artifacts,
)
from tech_cartography.evidence.openalex_limited_executor import (
  OpenAlexExecutionConfig,
  execute_openalex_limited,
  save_openalex_limited_artifacts,
)
from tech_cartography.manual.manual_fulltext_loader import (
  get_manual_fulltext_status,
  load_manual_fulltext_as_record,
)
from tech_cartography.reports.project_export import load_records_csv, save_records_csv
from tech_cartography.retrieval.bigquery_fulltext_availability_probe import (
  FulltextAvailabilityProbeResult,
  execute_availability_probe,
)
from tech_cartography.retrieval.publication_number_variants import (
  build_google_patents_url_variants,
  build_publication_number_variants,
  infer_country_kind_number,
)

DEFAULT_PUBLICATION_NUMBERS: tuple[str, ...] = (
  "US-12565719-B2",
  "US-12435451-B2",
  "US-12516451-B2",
)

DEMO_PUBLICATION_NUMBER = "US-12565719-B2"

SUMMARY_COLUMNS: tuple[str, ...] = (
  "publication_number",
  "title",
  "assignee",
  "country",
  "target_rank",
  "bigquery_row_exists",
  "claims_available",
  "description_available",
  "retrieval_route",
  "manual_input_exists",
  "query_plan_exists",
  "openalex_records_exists",
  "selected_evidence_papers_exists",
  "claim_paper_links_exists",
  "evidence_map_exists",
  "status",
  "confidence_limit",
  "next_action",
  "caveat",
)

CONFIDENCE_LIMIT = "claims_only / max medium, typically low/weak"
CAVEAT_TEXT = (
  "論文候補は特許主張の証明ではなく supporting evidence candidate です。"
  "FTO、侵害、有効性判断ではありません。"
)
MARKDOWN_CAUTION = (
  "このSmoke Runは、FTO、侵害、有効性判断ではありません。\n"
  "論文候補は特許主張の証明ではなく supporting evidence candidate です。\n"
  "claims_only または manual route の場合、confidenceは最大medium、基本はlow/weakです。\n"
  "架空情報は使いません。"
)

METADATA_SEARCH_PATHS: tuple[str, ...] = (
  "outputs/carbon_fiber_case_study/latest/top20_patents.csv",
  "outputs/carbon_fiber_case_study/latest/ranked_patents.csv",
  "outputs/carbon_fiber_case_study/latest/top5_fulltext_candidates.csv",
)

ProbeFn = Callable[..., FulltextAvailabilityProbeResult]


@dataclass
class ReproducibilitySmokeConfig:
  publication_numbers: list[str]
  output_dir: Path
  project_root: Path
  max_patents: int = 3
  skip_bigquery: bool = False
  use_existing_manual_inputs: bool = False
  build_query_plan_if_manual_exists: bool = False
  execute_openalex: bool = False
  plan_only_openalex: bool = True
  dry_run: bool = False
  manual_input_dir: Path | None = None


@dataclass
class PatentSmokeResult:
  publication_number: str
  title: str = ""
  assignee: str = ""
  country: str = "US"
  target_rank: str = ""
  bigquery_row_exists: bool = False
  claims_available: bool = False
  description_available: bool = False
  retrieval_route: str = ""
  manual_input_exists: bool = False
  query_plan_exists: bool = False
  openalex_records_exists: bool = False
  selected_evidence_papers_exists: bool = False
  claim_paper_links_exists: bool = False
  evidence_map_exists: bool = False
  status: str = ""
  confidence_limit: str = CONFIDENCE_LIMIT
  next_action: str = ""
  caveat: str = CAVEAT_TEXT
  error: str = ""
  blocked_cost_guard: bool = False
  openalex_plan_ready: bool = False
  manual_claims_present: bool = False
  probe_status: str = ""
  dry_run_note: str = ""

  def to_summary_row(self) -> dict[str, Any]:
    return {
      "publication_number": self.publication_number,
      "title": self.title,
      "assignee": self.assignee,
      "country": self.country,
      "target_rank": self.target_rank,
      "bigquery_row_exists": self.bigquery_row_exists,
      "claims_available": self.claims_available,
      "description_available": self.description_available,
      "retrieval_route": self.retrieval_route,
      "manual_input_exists": self.manual_input_exists,
      "query_plan_exists": self.query_plan_exists,
      "openalex_records_exists": self.openalex_records_exists,
      "selected_evidence_papers_exists": self.selected_evidence_papers_exists,
      "claim_paper_links_exists": self.claim_paper_links_exists,
      "evidence_map_exists": self.evidence_map_exists,
      "status": self.status,
      "confidence_limit": self.confidence_limit,
      "next_action": self.next_action,
      "caveat": self.caveat,
    }


@dataclass
class ReproducibilitySmokeRunResult:
  config: ReproducibilitySmokeConfig
  patents: list[PatentSmokeResult] = field(default_factory=list)
  dry_run: bool = False

  def summary_rows(self) -> list[dict[str, Any]]:
    return [p.to_summary_row() for p in self.patents]


def _csv_has_publication(path: Path, publication_number: str) -> bool:
  if not path.exists():
    return False
  try:
    rows = load_records_csv(path)
  except Exception:
    return False
  if not rows:
    return False
  if "publication_number" not in rows[0]:
    return True
  target = publication_number.upper().replace(" ", "")
  for row in rows:
    pub = str(row.get("publication_number") or "").upper().replace(" ", "").replace("-", "")
    if pub and pub == target.replace("-", ""):
      return True
  return False


def detect_artifact_flags(project_root: Path, publication_number: str) -> dict[str, bool]:
  ev_dir = project_root / "outputs" / "evidence_map_synthesis" / publication_number
  oa_dir = project_root / "outputs" / "openalex_limited_execution"
  per_oa_dir = oa_dir / publication_number

  evidence_map_md = (ev_dir / "evidence_map_synthesis.md").exists()
  evidence_map_json = (ev_dir / "evidence_map_synthesis.json").exists()

  selected_paths = [
    per_oa_dir / "selected_evidence_papers.csv",
    oa_dir / "selected_evidence_papers.csv",
  ]
  links_paths = [
    per_oa_dir / "claim_paper_candidate_links.csv",
    oa_dir / "claim_paper_candidate_links.csv",
  ]
  openalex_paths = [
    per_oa_dir / "openalex_paper_records.csv",
    oa_dir / "openalex_paper_records.csv",
  ]

  selected_exists = any(
    p.exists() and (not p.name.endswith(".csv") or _csv_has_publication(p, publication_number))
    for p in selected_paths
    if p.exists()
  )
  links_exists = any(
    p.exists() and _csv_has_publication(p, publication_number)
    for p in links_paths
    if p.exists()
  )
  openalex_exists = any(
    p.exists() and _csv_has_publication(p, publication_number)
    for p in openalex_paths
    if p.exists()
  )

  if publication_number == DEMO_PUBLICATION_NUMBER:
    demo_ready = (
      evidence_map_md
      and evidence_map_json
      and (oa_dir / "selected_evidence_papers.csv").exists()
      and (oa_dir / "claim_paper_candidate_links.csv").exists()
    )
  else:
    demo_ready = evidence_map_md and evidence_map_json

  return {
    "evidence_map_md": evidence_map_md,
    "evidence_map_json": evidence_map_json,
    "evidence_map_exists": bool(demo_ready),
    "selected_evidence_papers_exists": selected_exists,
    "claim_paper_links_exists": links_exists,
    "openalex_records_exists": openalex_exists,
  }


def detect_query_plan_exists(
  output_dir: Path,
  publication_number: str,
  *,
  project_root: Path | None = None,
) -> bool:
  per_patent = output_dir / "per_patent" / publication_number / "paper_query_candidates_from_claims.csv"
  root = project_root or Path(".")
  legacy = root / "outputs/claims_paper_query_plans" / publication_number / "paper_query_candidates_from_claims.csv"
  return per_patent.exists() or legacy.exists()


def load_patent_metadata(project_root: Path, publication_number: str) -> dict[str, str]:
  for relative in METADATA_SEARCH_PATHS:
    path = project_root / relative
    if not path.exists():
      continue
    try:
      rows = load_records_csv(path)
    except Exception:
      continue
    target = publication_number.upper().replace(" ", "")
    for index, row in enumerate(rows, start=1):
      pub = str(row.get("publication_number") or "").upper().replace(" ", "")
      if pub.replace("-", "") != target.replace("-", ""):
        continue
      return {
        "title": str(row.get("title") or ""),
        "assignee": str(row.get("assignee") or ""),
        "country": str(row.get("country") or infer_country_kind_number(publication_number).get("country") or "US"),
        "target_rank": str(row.get("rank") or row.get("target_rank") or index),
      }
  inferred = infer_country_kind_number(publication_number)
  return {
    "title": "",
    "assignee": "",
    "country": inferred.get("country") or "US",
    "target_rank": "",
  }


def _retrieval_route_from_probe(probe: FulltextAvailabilityProbeResult) -> str:
  if probe.probe_status == "skipped_due_to_probe_cost":
    return "blocked_cost_guard"
  if probe.has_claims or probe.probe_status == "found_claims":
    return "bigquery_fulltext"
  if probe.probe_status in {
    "manual_route_recommended",
    "found_metadata_only",
    "not_found_in_bigquery",
    "found_description_only",
    "publication_number_format_mismatch",
  }:
    return "manual_route_required"
  if probe.has_publication_row:
    return "manual_route_required"
  return "unknown"


def resolve_patent_status(result: PatentSmokeResult) -> str:
  if result.error:
    return "error"
  if result.blocked_cost_guard:
    return "blocked_cost_guard"
  if result.evidence_map_exists:
    if result.publication_number == DEMO_PUBLICATION_NUMBER:
      return "complete_existing_demo"
    return "evidence_map_ready"
  if result.openalex_records_exists or result.openalex_plan_ready:
    return "openalex_plan_ready"
  if result.query_plan_exists:
    return "query_plan_ready"
  if result.manual_input_exists and result.manual_claims_present:
    return "manual_claims_available"
  if result.claims_available:
    return "bigquery_fulltext_available"
  if result.retrieval_route == "manual_route_required" and not result.manual_input_exists:
    return "blocked_missing_manual_claims"
  if result.retrieval_route == "manual_route_required":
    return "manual_route_required"
  return "manual_route_required"


def resolve_next_action(status: str) -> str:
  mapping = {
    "complete_existing_demo": "既存デモ成果物をUIで確認し、追加特許との比較を行う",
    "evidence_map_ready": "Evidence Map成果物をレビューし、再現性の差分を記録する",
    "openalex_plan_ready": "OpenAlex実行は別確認後に --execute-openalex で実施する",
    "query_plan_ready": "OpenAlex plan_only を確認し、必要なら limited execution を実行する",
    "manual_claims_available": "claim extraction / query plan 生成を続行する",
    "bigquery_fulltext_available": "BigQuery fulltext 取得フローへ進める（別スクリプト）",
    "manual_route_required": "Manual Claims Route: Google Patents から claims を import する",
    "blocked_missing_manual_claims": "next_manual_claims_checklist.md の import 手順で claims を追加する",
    "blocked_cost_guard": "cost guard 解除または手動 route で claims を追加する",
    "error": "error 詳細を確認し、対象特許を個別に再実行する",
  }
  return mapping.get(status, "状況を確認してください")


def build_import_command_example(publication_number: str, project_root: Path) -> str:
  urls = build_google_patents_url_variants(publication_number)
  url = urls[0] if urls else f"https://patents.google.com/patent/{publication_number}"
  claims_file = project_root / "inputs" / "manual" / f"{publication_number}_claims.txt"
  return (
    "python scripts/import_manual_fulltext.py \\\n"
    f"  --publication-number {publication_number} \\\n"
    f"  --source-url {url} \\\n"
    f"  --claims-file {claims_file} \\\n"
    "  --input-route manual_google_patents \\\n"
    "  --entered-by local_user"
  )


def render_manual_claims_checklist(
  patents: list[PatentSmokeResult],
  project_root: Path,
) -> str:
  lines = [
    "# Next Manual Claims Checklist",
    "",
    "manual claims が必要な特許の確認・import 手順です。",
    "Google Patents URL は機械生成です。**実際に取得できるかはユーザー確認事項**です。",
    "自動スクレイピングは行いません。",
    "",
  ]
  targets = [
    p
    for p in patents
    if p.status in {"blocked_missing_manual_claims", "manual_route_required"}
    or (p.retrieval_route == "manual_route_required" and not p.manual_claims_present)
  ]
  if not targets:
    lines.append("現時点で manual claims の追加が必要な特許はありません。")
    return "\n".join(lines) + "\n"

  for patent in targets:
    urls = build_google_patents_url_variants(patent.publication_number)
    url = urls[0] if urls else f"https://patents.google.com/patent/{patent.publication_number}"
    claims_file = project_root / "inputs" / "manual" / f"{patent.publication_number}_claims.txt"
    lines.extend(
      [
        f"## {patent.publication_number}",
        "",
        f"- publication_number: {patent.publication_number}",
        f"- Google Patents URL候補: {url}",
        f"- claims file path候補: `{claims_file}`",
        "- import command例:",
        "",
        "```bash",
        build_import_command_example(patent.publication_number, project_root),
        "```",
        "",
        "> 注意: URLとファイルパスは候補です。claims 本文の取得は手動で行ってください。",
        "",
      ],
    )
  return "\n".join(lines)


def render_reproducibility_summary_markdown(run: ReproducibilitySmokeRunResult) -> str:
  lines = [
    "# Phase22 Reproducibility Smoke Run",
    "",
    "## 目的",
    "",
    "US-12565719-B2 以外の特許候補について、Evidence Map パイプラインの再現性を診断します。",
    "「1件だけの偶然ではないか？」に答えるため、availability / manual route / blocked 理由を記録します。",
    "",
    "## 対象特許",
    "",
  ]
  for patent in run.patents:
    lines.append(f"- {patent.publication_number} — status: `{patent.status}`")
  lines.extend(["", "## 結果サマリー", ""])
  for patent in run.patents:
    lines.append(
      f"- **{patent.publication_number}**: {patent.status} / route={patent.retrieval_route or 'n/a'} "
      f"/ next: {patent.next_action}",
    )

  lines.extend(["", "## 特許別メモ", ""])
  for index, patent in enumerate(run.patents, start=1):
    if index == 1 and patent.publication_number == DEMO_PUBLICATION_NUMBER:
      headline = f"### {index}件目: {patent.publication_number} — Evidence Map デモ（既存成果物）"
    else:
      headline = f"### {index}件目: {patent.publication_number}"
    lines.append(headline)
    lines.append("")
    lines.append(f"- status: `{patent.status}`")
    lines.append(f"- BigQuery row: {patent.bigquery_row_exists}")
    lines.append(f"- claims available: {patent.claims_available}")
    lines.append(f"- description available: {patent.description_available}")
    lines.append(f"- retrieval route: {patent.retrieval_route or 'n/a'}")
    lines.append(f"- manual input: {patent.manual_input_exists}")
    lines.append(f"- query plan: {patent.query_plan_exists}")
    lines.append(f"- evidence map: {patent.evidence_map_exists}")
    if patent.error:
      lines.append(f"- error: {patent.error}")
    lines.append("")

  reproduced = [p.publication_number for p in run.patents if p.status not in {"error", "blocked_cost_guard"}]
  blocked = [p.publication_number for p in run.patents if p.status.startswith("blocked")]
  lines.extend(
    [
      "## 何が再現できたか",
      "",
      f"- 診断完了: {', '.join(reproduced) if reproduced else '(なし)'}",
      "",
      "## 何がまだ未確認か",
      "",
      f"- blocked / manual待ち: {', '.join(blocked) if blocked else '(なし)'}",
      "",
      "## 次に必要な manual action",
      "",
      "- `next_manual_claims_checklist.md` を参照し、claims 未入力の特許を import してください。",
      "",
      "## 重要な注意",
      "",
      MARKDOWN_CAUTION,
      "",
    ],
  )
  if run.dry_run:
    lines.extend(["## Dry Run", "", "外部 API / BigQuery は実行していません。実行予定のみ記録しました。", ""])
  return "\n".join(lines)


def _build_query_plan_for_patent(
  publication_number: str,
  manual_dir: Path,
  output_dir: Path,
  metadata: dict[str, str],
) -> tuple[bool, bool]:
  record = load_manual_fulltext_as_record(publication_number, manual_dir, base_metadata=metadata)
  if record is None:
    return False, False
  plan = build_claims_paper_query_plan([record], {"elements": []})
  per_patent_dir = output_dir / "per_patent" / publication_number
  save_claims_paper_query_artifacts(plan, per_patent_dir, include_quality_report=True)
  plan_ready = bool(plan.get("plan_ready_for_openalex"))
  return True, plan_ready


def _run_openalex_for_patent(
  publication_number: str,
  output_dir: Path,
  *,
  execute: bool,
  plan_only: bool,
) -> tuple[bool, bool]:
  per_patent_dir = output_dir / "per_patent" / publication_number
  csv_path = per_patent_dir / "paper_query_candidates_from_claims.csv"
  if not csv_path.exists():
    return False, False
  candidates = load_records_csv(csv_path)
  if not candidates:
    return False, False
  config = OpenAlexExecutionConfig(
    execute_openalex=bool(execute),
    output_dir=str(per_patent_dir / "openalex"),
    max_queries=3,
    max_results_per_query=5,
  )
  result = execute_openalex_limited(candidates, config, publication_number=publication_number)
  if execute:
    save_openalex_limited_artifacts(result, config.output_dir)
    records_exist = bool(result.get("paper_records"))
    return records_exist, not records_exist and plan_only
  plan_ready = bool(result.get("selected_queries")) or str(result.get("execution_status")) == "plan_only"
  return False, plan_ready


def process_patent_smoke(
  publication_number: str,
  config: ReproducibilitySmokeConfig,
  *,
  probe_fn: ProbeFn | None = None,
) -> PatentSmokeResult:
  manual_dir = config.manual_input_dir or (config.project_root / "outputs" / "manual_fulltext_inputs")
  metadata = load_patent_metadata(config.project_root, publication_number)
  result = PatentSmokeResult(
    publication_number=publication_number,
    title=metadata.get("title", ""),
    assignee=metadata.get("assignee", ""),
    country=metadata.get("country", "US"),
    target_rank=str(metadata.get("target_rank", "")),
  )

  artifacts = detect_artifact_flags(config.project_root, publication_number)
  result.evidence_map_exists = artifacts["evidence_map_exists"]
  result.selected_evidence_papers_exists = artifacts["selected_evidence_papers_exists"]
  result.claim_paper_links_exists = artifacts["claim_paper_links_exists"]
  result.openalex_records_exists = artifacts["openalex_records_exists"]
  result.query_plan_exists = detect_query_plan_exists(
    config.output_dir,
    publication_number,
    project_root=config.project_root,
  )

  manual_status = get_manual_fulltext_status(publication_number, manual_dir)
  result.manual_input_exists = bool(manual_status.get("manual_input_exists"))
  result.manual_claims_present = bool(manual_status.get("claims_present"))

  if config.dry_run:
    result.dry_run_note = "dry_run: external APIs skipped"
    if result.evidence_map_exists:
      result.retrieval_route = "existing_evidence_map"
    elif result.manual_claims_present:
      result.retrieval_route = "manual_claims_route"
    elif config.skip_bigquery:
      result.retrieval_route = "probe_skipped"
    else:
      result.retrieval_route = "manual_route_required"
    result.status = resolve_patent_status(result)
    result.next_action = resolve_next_action(result.status)
    return result

  try:
    if not config.skip_bigquery:
      probe_runner = probe_fn or execute_availability_probe
      probe = probe_runner(
        publication_number,
        variants=build_publication_number_variants(publication_number),
        execute=True,
      )
      result.probe_status = probe.probe_status
      result.bigquery_row_exists = bool(probe.has_publication_row)
      result.claims_available = bool(probe.has_claims)
      result.description_available = bool(probe.has_description)
      result.retrieval_route = _retrieval_route_from_probe(probe)
      result.blocked_cost_guard = probe.probe_status == "skipped_due_to_probe_cost"
    elif result.manual_claims_present:
      result.retrieval_route = "manual_claims_route"
    else:
      result.retrieval_route = "probe_skipped"

    if (
      config.use_existing_manual_inputs
      and config.build_query_plan_if_manual_exists
      and result.manual_claims_present
      and not result.blocked_cost_guard
    ):
      built, plan_ready = _build_query_plan_for_patent(
        publication_number,
        manual_dir,
        config.output_dir,
        metadata,
      )
      result.query_plan_exists = result.query_plan_exists or built
      result.openalex_plan_ready = plan_ready

    if (
      result.query_plan_exists
      and (config.plan_only_openalex or config.execute_openalex)
      and not result.blocked_cost_guard
    ):
      records_exist, plan_ready = _run_openalex_for_patent(
        publication_number,
        config.output_dir,
        execute=config.execute_openalex,
        plan_only=config.plan_only_openalex,
      )
      result.openalex_records_exists = result.openalex_records_exists or records_exist
      result.openalex_plan_ready = result.openalex_plan_ready or plan_ready

    result.status = resolve_patent_status(result)
    result.next_action = resolve_next_action(result.status)
    return result
  except Exception as exc:  # noqa: BLE001
    result.error = str(exc)
    result.status = "error"
    result.next_action = resolve_next_action("error")
    result.caveat = f"{CAVEAT_TEXT} error={result.error}"
    return result


def run_reproducibility_smoke(
  config: ReproducibilitySmokeConfig,
  *,
  probe_fn: ProbeFn | None = None,
) -> ReproducibilitySmokeRunResult:
  pubs = list(config.publication_numbers)[: max(1, int(config.max_patents))]
  run = ReproducibilitySmokeRunResult(config=config, dry_run=bool(config.dry_run))
  for publication_number in pubs:
    patent_result = process_patent_smoke(publication_number, config, probe_fn=probe_fn)
    if not patent_result.status:
      patent_result.status = resolve_patent_status(patent_result)
    if not patent_result.next_action:
      patent_result.next_action = resolve_next_action(patent_result.status)
    run.patents.append(patent_result)
  return run


def save_reproducibility_outputs(
  run: ReproducibilitySmokeRunResult,
  output_dir: Path | None = None,
) -> dict[str, str]:
  out = Path(output_dir or run.config.output_dir)
  out.mkdir(parents=True, exist_ok=True)
  rows = run.summary_rows()

  csv_path = out / "reproducibility_summary.csv"
  json_path = out / "reproducibility_summary.json"
  md_path = out / "reproducibility_summary.md"
  checklist_path = out / "next_manual_claims_checklist.md"

  save_records_csv(rows, csv_path)
  json_path.write_text(
    json.dumps(
      {
        "dry_run": run.dry_run,
        "publication_numbers": [p.publication_number for p in run.patents],
        "summary": rows,
      },
      indent=2,
      ensure_ascii=False,
    ),
    encoding="utf-8",
  )
  md_path.write_text(render_reproducibility_summary_markdown(run), encoding="utf-8")
  checklist_path.write_text(
    render_manual_claims_checklist(run.patents, run.config.project_root),
    encoding="utf-8",
  )
  return {
    "reproducibility_summary_csv": str(csv_path),
    "reproducibility_summary_json": str(json_path),
    "reproducibility_summary_md": str(md_path),
    "next_manual_claims_checklist_md": str(checklist_path),
  }
