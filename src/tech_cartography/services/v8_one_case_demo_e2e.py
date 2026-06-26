"""v8 One Case Real Demo E2E service (Phase 27N.5)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from tech_cartography.runtime.v8_one_case_demo_schema import (
  DEFAULT_ONE_CASE_ID,
  DEFAULT_ONE_CASE_INPUT_CSV,
  ONE_CASE_DEMO_SAFETY_NOTICES,
  V8OneCaseDemoStepStatus,
  V8OneCaseDemoSummary,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_claim_input_loader import load_claims_input_csv
from tech_cartography.services.v8_demo_polish import build_demo_polish_report
from tech_cartography.services.v8_demo_polish_export import export_demo_polish, find_latest_demo_polish_dir
from tech_cartography.services.v8_demo_readiness import assess_case_demo_readiness, build_demo_readiness_report
from tech_cartography.services.v8_demo_readiness_export import export_demo_readiness
from tech_cartography.services.v8_large_candidate_import import import_large_candidates
from tech_cartography.services.v8_large_candidate_shortlist import (
  build_staged_shortlist,
  find_latest_large_shortlist_dir,
  load_top5_publications,
)
from tech_cartography.services.v8_manual_claim_refresh import refresh_after_manual_claim
from tech_cartography.services.v8_sources_table import project_root_from_here

LOCAL_ONE_CASE_DEMO_SUBDIR = "local_v8_one_case_demo"


@dataclass
class OneCaseDemoRunOptions:
  case_id: str = DEFAULT_ONE_CASE_ID
  input_csv: str = DEFAULT_ONE_CASE_INPUT_CSV
  max_rows: int = 1000
  skip_import: bool = False
  skip_shortlist: bool = False
  skip_refresh: bool = False
  skip_demo_polish: bool = False
  skip_readiness: bool = False
  project_root: Path | str | None = None


def _output_dir(project_root: Path) -> Path:
  base = project_root / "outputs" / LOCAL_ONE_CASE_DEMO_SUBDIR
  slug = utc_now_iso().replace(":", "").replace("-", "").replace("+00:00", "Z")
  out = base / f"e2e_{slug}"
  out.mkdir(parents=True, exist_ok=True)
  return out


def _count_claim_stats(case_id: str, root: Path) -> tuple[int, int, list[tuple[str, str]]]:
  rows, _ = load_claims_input_csv(case_id, project_root=root)
  loaded = [r for r in rows if r.has_loaded_text()]
  not_loaded = [r for r in rows if not r.has_loaded_text()]
  loaded_pairs = [(r.publication_number, r.claim_no) for r in loaded if r.publication_number]
  return len(loaded), len(not_loaded), loaded_pairs


def assess_one_case_demo_status(
  *,
  case_id: str = DEFAULT_ONE_CASE_ID,
  input_csv: str = DEFAULT_ONE_CASE_INPUT_CSV,
  project_root: Path | str | None = None,
) -> V8OneCaseDemoSummary:
  """Read-only assessment — no import, no claim generation."""
  root = Path(project_root or project_root_from_here())
  csv_path = root / input_csv
  summary = V8OneCaseDemoSummary(
    case_id=case_id,
    generated_at=utc_now_iso(),
    input_csv_path=str(csv_path),
    input_csv_exists=csv_path.is_file(),
  )

  large_csv = root / "cases" / case_id / "source_candidates_large.csv"
  deduped_csv = root / "cases" / case_id / "source_candidates_large_deduped.csv"
  if large_csv.is_file():
    summary.imported_count = max(0, sum(1 for _ in large_csv.open(encoding="utf-8")) - 1)
  if deduped_csv.is_file():
    summary.deduped_count = max(0, sum(1 for _ in deduped_csv.open(encoding="utf-8")) - 1)

  shortlist_dir = find_latest_large_shortlist_dir(case_id, root)
  if shortlist_dir and shortlist_dir.is_dir():
    manifest_path = shortlist_dir / "large_candidate_shortlist_manifest.json"
    if manifest_path.is_file():
      try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        sel = data.get("selection") or data
        summary.top100_count = sel.get("top100_count")
        summary.top20_count = sel.get("top20_count")
        summary.top5_count = sel.get("top5_count")
        summary.deduped_count = summary.deduped_count or sel.get("deduped_count")
      except json.JSONDecodeError:
        pass

  summary.top5_publication_numbers = load_top5_publications(case_id, project_root=root)
  manual, required, _ = _count_claim_stats(case_id, root)
  summary.manual_claim_count = manual
  summary.claim_text_required_count = required

  readiness = assess_case_demo_readiness(case_id, project_root=root)
  summary.demo_readiness_status = readiness.overall_status
  summary.evidence_link_count = readiness.evidence_link_count
  summary.gap_count = readiness.gap_count

  polish_dir = find_latest_demo_polish_dir(case_id, project_root=root)
  if polish_dir:
    summary.demo_polish_pack_path = str(polish_dir)

  summary.next_user_action = _resolve_next_action(summary)
  summary.overall_status = _resolve_overall_status(summary)
  return summary


def _resolve_next_action(summary: V8OneCaseDemoSummary) -> str:
  if not summary.input_csv_exists and not (summary.imported_count or 0) > 0:
    return (
      f"実在特許 CSV を配置してください: {summary.input_csv_path}"
      " — BigQuery等で別途抽出した CSV のみ（fixture/架空CSV不可）"
    )
  if not summary.top5_publication_numbers:
    return "Large Candidate Import → Top100/Top20/Top5 を生成してください"
  if summary.manual_claim_count < 1:
    pubs = ", ".join(summary.top5_publication_numbers[:5])
    return (
      f"Claim Map タブで Top5 のうち1件だけ claim 本文を手動投入してください。"
      f" 候補 publication_number: {pubs}"
    )
  if not summary.demo_polish_pack_path:
    return "Demo Polish Pack を生成してください"
  if summary.demo_readiness_status in {"not_ready", "needs_large_candidate_csv", "needs_shortlist"}:
    return "Demo Readiness Pack を再生成し、Case 1 の readiness を確認してください"
  return "Case 1 デモ準備完了 — UI で Export / はじめにタブを確認"


def _resolve_overall_status(summary: V8OneCaseDemoSummary) -> str:
  if not summary.input_csv_exists and not (summary.imported_count or 0) > 0:
    return "needs_input_csv"
  if not summary.top5_publication_numbers:
    return "needs_shortlist"
  if summary.manual_claim_count < 1:
    return "needs_manual_claim"
  if summary.demo_readiness_status in {"demo_ready", "ready_with_warnings", "partial_claim_loaded"}:
    return "demo_ready"
  if summary.demo_polish_pack_path:
    return "ready_with_warnings"
  return "in_progress"


def run_one_case_demo_e2e(options: OneCaseDemoRunOptions) -> tuple[V8OneCaseDemoSummary, int]:
  """Run Case 1 E2E pipeline. Does not generate claim text or call external APIs."""
  root = Path(options.project_root or project_root_from_here())
  csv_path = root / options.input_csv
  steps: list[V8OneCaseDemoStepStatus] = []
  warnings: list[str] = list(ONE_CASE_DEMO_SAFETY_NOTICES[:2])

  summary = V8OneCaseDemoSummary(
    case_id=options.case_id,
    generated_at=utc_now_iso(),
    input_csv_path=str(csv_path),
    input_csv_exists=csv_path.is_file(),
  )

  large_exists = (root / "cases" / options.case_id / "source_candidates_large.csv").is_file()

  if not summary.input_csv_exists and not large_exists:
    summary.next_user_action = _resolve_next_action(summary)
    summary.overall_status = "needs_input_csv"
    summary.warnings.append(
      "input CSV がありません — fixture や架空1000件 CSV は使用しません。"
    )
    out = _output_dir(root)
    summary.output_dir = str(out)
    summary.manifest_path = _write_manifest(summary, out)
    return summary, 1

  if not options.skip_import:
    if not summary.input_csv_exists and large_exists:
      warnings.append("input CSV なし — 既存 source_candidates_large.csv を使用")
      steps.append(V8OneCaseDemoStepStatus(
        step_id="import",
        step_name="large_candidate_import",
        status="skipped",
        summary="既存 large CSV を使用",
      ))
    else:
      try:
        result = import_large_candidates(
          case_id=options.case_id,
          input_path=csv_path,
          max_rows=options.max_rows,
          project_root=root,
        )
        summary.imported_count = result.accepted_row_count
        steps.append(V8OneCaseDemoStepStatus(
          step_id="import",
          step_name="large_candidate_import",
          status="pass" if result.accepted_row_count > 0 else "fail",
          summary=f"accepted={result.accepted_row_count}",
        ))
        if result.accepted_row_count <= 0:
          summary.next_user_action = "import 失敗 — CSV 内容を確認"
          summary.overall_status = "import_failed"
          out = _output_dir(root)
          summary.output_dir = str(out)
          summary.manifest_path = _write_manifest(summary, out)
          return summary, 1
      except Exception as exc:
        steps.append(V8OneCaseDemoStepStatus(
          step_id="import",
          step_name="large_candidate_import",
          status="fail",
          summary=str(exc),
        ))
        summary.next_user_action = f"import 失敗: {exc}"
        summary.overall_status = "import_failed"
        out = _output_dir(root)
        summary.output_dir = str(out)
        summary.manifest_path = _write_manifest(summary, out)
        return summary, 1

  if not options.skip_shortlist:
    try:
      pack = build_staged_shortlist(options.case_id, project_root=root)
      sel = pack.selection
      summary.imported_count = summary.imported_count or sel.population_count
      summary.deduped_count = sel.deduped_count
      summary.top100_count = sel.top100_count
      summary.top20_count = sel.top20_count
      summary.top5_count = sel.top5_count
      steps.append(V8OneCaseDemoStepStatus(
        step_id="shortlist",
        step_name="large_candidate_shortlist",
        status="pass" if sel.top5_count >= 1 else "fail",
        summary=f"Top5={sel.top5_count}",
      ))
      if sel.top5_count < 1:
        summary.next_user_action = "shortlist 失敗 — large candidate を確認"
        summary.overall_status = "shortlist_failed"
        out = _output_dir(root)
        summary.output_dir = str(out)
        summary.manifest_path = _write_manifest(summary, out)
        return summary, 1
    except Exception as exc:
      steps.append(V8OneCaseDemoStepStatus(
        step_id="shortlist",
        step_name="large_candidate_shortlist",
        status="fail",
        summary=str(exc),
      ))
      summary.next_user_action = f"shortlist 失敗: {exc}"
      summary.overall_status = "shortlist_failed"
      out = _output_dir(root)
      summary.output_dir = str(out)
      summary.manifest_path = _write_manifest(summary, out)
      return summary, 1

  summary.top5_publication_numbers = load_top5_publications(options.case_id, project_root=root)
  manual, required, loaded_pairs = _count_claim_stats(options.case_id, root)
  summary.manual_claim_count = manual
  summary.claim_text_required_count = required

  if manual >= 1 and not options.skip_refresh:
    pub, cno = loaded_pairs[0]
    try:
      refresh_after_manual_claim(
        case_id=options.case_id,
        publication_number=pub,
        claim_no=cno,
        project_root=root,
      )
      steps.append(V8OneCaseDemoStepStatus(
        step_id="refresh",
        step_name="manual_claim_refresh",
        status="pass",
        summary=f"refreshed {pub} claim {cno}",
      ))
    except Exception as exc:
      steps.append(V8OneCaseDemoStepStatus(
        step_id="refresh",
        step_name="manual_claim_refresh",
        status="fail",
        summary=str(exc),
      ))
      warnings.append(f"refresh 失敗: {exc}")
  elif manual < 1:
    steps.append(V8OneCaseDemoStepStatus(
      step_id="refresh",
      step_name="manual_claim_refresh",
      status="skipped",
      summary="claim 未投入 — 手動投入後に refresh",
      next_user_action="Claim Map タブで claim 本文を1件手動投入",
    ))

  if not options.skip_demo_polish:
    if manual >= 1:
      try:
        polish = build_demo_polish_report(case_id=options.case_id, project_root=root)
        polish_exp = export_demo_polish(polish, project_root=root)
        summary.demo_polish_pack_path = polish_exp.output_dir
        if polish.evidence_demo_status:
          summary.evidence_link_count = polish.evidence_demo_status.evidence_link_count
          summary.claim_text_required_count = polish.evidence_demo_status.claim_text_required_count
        if polish.gap_demo_status:
          summary.gap_count = polish.gap_demo_status.gap_count
        steps.append(V8OneCaseDemoStepStatus(
          step_id="polish",
          step_name="demo_polish_pack",
          status="pass",
          summary=polish_exp.output_dir,
        ))
      except Exception as exc:
        warnings.append(f"demo polish 失敗: {exc}")
    else:
      steps.append(V8OneCaseDemoStepStatus(
        step_id="polish",
        step_name="demo_polish_pack",
        status="skipped",
        summary="claim 未投入のため skip",
      ))

  if not options.skip_readiness:
    try:
      dr = build_demo_readiness_report(project_root=root)
      export_demo_readiness(dr, project_root=root)
      case_r = next((c for c in dr.cases if c.case_id == options.case_id), None)
      if case_r:
        summary.demo_readiness_status = case_r.overall_status
        summary.evidence_link_count = case_r.evidence_link_count
        summary.gap_count = case_r.gap_count
        summary.manual_claim_count = case_r.manual_claim_count or summary.manual_claim_count
      steps.append(V8OneCaseDemoStepStatus(
        step_id="readiness",
        step_name="demo_readiness_pack",
        status="pass",
        summary=summary.demo_readiness_status,
      ))
    except Exception as exc:
      warnings.append(f"demo readiness 失敗: {exc}")

  summary.step_statuses = steps
  summary.warnings = warnings
  summary.next_user_action = _resolve_next_action(summary)
  summary.overall_status = _resolve_overall_status(summary)

  out = _output_dir(root)
  summary.output_dir = str(out)
  summary.manifest_path = _write_manifest(summary, out)

  exit_code = 0
  if summary.overall_status in {"needs_input_csv", "import_failed", "shortlist_failed"}:
    exit_code = 1
  return summary, exit_code


def _write_manifest(summary: V8OneCaseDemoSummary, output_dir: Path) -> str:
  manifest_path = output_dir / "one_case_demo_e2e_manifest.json"
  payload = {
    "export_id": f"one_case_demo_{uuid.uuid4().hex[:12]}",
    "summary": summary.to_dict(),
    "safety_notices": list(ONE_CASE_DEMO_SAFETY_NOTICES),
  }
  manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
  summary_path = output_dir / "one_case_demo_e2e_summary.json"
  summary_path.write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
  return str(manifest_path)
