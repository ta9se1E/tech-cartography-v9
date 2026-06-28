"""v8 Large Candidate staged shortlist (Phase 27J.0 / 27J.1)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tech_cartography.runtime.v8_large_candidate_schema import (
  LARGE_CANDIDATE_SAFETY_NOTICES,
  V8LargeCandidateRecord,
  V8LargeCandidateShortlistPack,
  V8LargeCandidateStageSelection,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_large_candidate_import import (
  load_large_candidates_csv,
  records_to_csv,
)
from tech_cartography.services.v8_large_candidate_normalizer import normalize_and_dedupe_large_candidates
from tech_cartography.services.v8_large_candidate_ranking_explanation import (
  build_ranking_explanation_report,
  export_ranking_explanation,
)
from tech_cartography.services.v8_patent_triage_adapter import score_large_candidates_with_triage
from tech_cartography.services.v8_theme_based_ranking_policy import (
  build_dropped_from_top5_summary,
  build_theme_based_ranking_policy,
  enrich_top5_record_with_theme,
  select_top5_preserving_existing,
)
from tech_cartography.services.v8_research_theme_defaults import load_research_theme_profile
from tech_cartography.services.v8_sources_table import project_root_from_here

LOCAL_LARGE_SHORTLIST_SUBDIR = "local_v8_large_shortlists"


def get_large_shortlist_dir(case_id: str, project_root: Path | str | None = None) -> Path:
  if not case_id or not str(case_id).strip():
    raise ValueError("case_id must be a non-empty string")
  root = Path(project_root or project_root_from_here())
  return root / "outputs" / LOCAL_LARGE_SHORTLIST_SUBDIR / case_id


def _large_shortlist_base_dir(project_root: Path | str | None = None) -> Path:
  root = Path(project_root or project_root_from_here())
  return root / "outputs" / LOCAL_LARGE_SHORTLIST_SUBDIR


def _pack_population_count(pack_dir: Path) -> int:
  manifest_path = pack_dir / "large_candidate_shortlist_manifest.json"
  if not manifest_path.exists():
    return 0
  try:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return int((manifest.get("selection") or {}).get("population_count") or 0)
  except (json.JSONDecodeError, TypeError, ValueError):
    return 0


def _preferred_pack_dir(pack_dirs: list[Path]) -> Path | None:
  if not pack_dirs:
    return None
  return max(pack_dirs, key=lambda p: (_pack_population_count(p), p.stat().st_mtime))


def find_latest_large_shortlist_dir(
  case_id: str | None,
  project_root: Path | str | None = None,
) -> Path | None:
  if not case_id:
    return find_latest_large_shortlist_dir_for_any_case(project_root)
  base = get_large_shortlist_dir(case_id, project_root)
  if not base.is_dir():
    return None
  dirs = [p for p in base.iterdir() if p.is_dir()]
  return _preferred_pack_dir(dirs)


def find_latest_large_shortlist_dirs_for_all_cases(
  project_root: Path | str | None = None,
) -> list[tuple[str, Path]]:
  base = _large_shortlist_base_dir(project_root)
  if not base.is_dir():
    return []
  results: list[tuple[str, Path]] = []
  for case_dir in sorted(p for p in base.iterdir() if p.is_dir()):
    latest = find_latest_large_shortlist_dir(case_dir.name, project_root)
    if latest and latest.exists():
      results.append((case_dir.name, latest))
  return results


def find_latest_large_shortlist_dir_for_any_case(
  project_root: Path | str | None = None,
) -> Path | None:
  all_packs = find_latest_large_shortlist_dirs_for_all_cases(project_root)
  if not all_packs:
    return None
  return max(all_packs, key=lambda item: (_pack_population_count(item[1]), item[1].stat().st_mtime))[1]


def safe_find_latest_large_shortlist_dir(
  case_id: str | None,
  project_root: Path | str | None = None,
) -> Path | None:
  if case_id:
    return find_latest_large_shortlist_dir(case_id, project_root)
  return find_latest_large_shortlist_dir_for_any_case(project_root)


def find_latest_large_manifest(case_id: str, project_root: Path | str | None = None) -> Path | None:
  latest = find_latest_large_shortlist_dir(case_id, project_root)
  if latest:
    manifest = latest / "large_candidate_shortlist_manifest.json"
    if manifest.exists():
      return manifest
  base = get_large_shortlist_dir(case_id, project_root)
  flat = base / "large_candidate_shortlist_manifest.json"
  return flat if flat.exists() else None


def _pack_id(case_id: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{utc_now_iso()}".encode()).hexdigest()[:12]
  return f"{case_id}:large_shortlist:{digest}"


def _selection_id(case_id: str) -> str:
  digest = hashlib.sha256(f"{case_id}|selection".encode()).hexdigest()[:12]
  return f"{case_id}:stage_selection:{digest}"


def _search_blob(rec: V8LargeCandidateRecord) -> str:
  return " ".join([
    rec.title, rec.abstract, rec.organization, rec.assignee, rec.publication_number,
  ]).lower()


def score_candidate(
  rec: V8LargeCandidateRecord,
  *,
  case_id: str,
  include_keywords: tuple[str, ...] = (),
  exclude_keywords: tuple[str, ...] = (),
) -> tuple[float, str, list[str]]:
  """Phase27J.0 fallback heuristic — used when patent_triage adapter falls back."""
  from tech_cartography.runtime.v8_large_candidate_schema import CASE_KEYWORDS

  keywords = list(CASE_KEYWORDS.get(case_id, ())) + list(include_keywords)
  blob = _search_blob(rec)
  matched = [kw for kw in keywords if kw.lower() in blob]
  excluded = [kw for kw in exclude_keywords if kw.lower() in blob]

  score = len(matched) * 0.12
  reasons: list[str] = []
  if matched:
    reasons.append(f"keyword_hits={len(matched)}")
  if rec.publication_number:
    score += 0.15
    reasons.append("has_publication_number")
  if rec.year:
    score += 0.08
    reasons.append("has_year")
  if rec.title:
    score += 0.05
    reasons.append("title present")
  else:
    score -= 0.2
    reasons.append("missing_title_penalty")
  if not rec.publication_number:
    score -= 0.15
    reasons.append("missing_pub_penalty")
  if rec.source_type == "patent":
    score += 0.1
    reasons.append("patent_priority")
  if excluded:
    score -= 0.25 * len(excluded)
    reasons.append(f"excluded_hits={len(excluded)}")

  score = max(0.0, min(1.0, score))
  reason = "; ".join(reasons) or "baseline_heuristic"
  return score, reason, matched


def _enrich_stage_records(
  items: list[V8LargeCandidateRecord],
  *,
  label: str,
  ranking_policy: str,
  start_rank: int = 1,
  theme_profile=None,
) -> list[V8LargeCandidateRecord]:
  out: list[V8LargeCandidateRecord] = []
  for i, rec in enumerate(items):
    copy = V8LargeCandidateRecord.from_dict(rec.to_dict())
    copy.stage_label = label
    copy.selected_stage = label
    copy.rank = start_rank + i
    copy.ranking_policy = ranking_policy
    copy.next_verification_action = (
      f"原典で {copy.publication_number or copy.title[:30]} を人手確認"
      if label == "top5"
      else f"候補スクリーニング: {copy.publication_number or 'no pub'}"
    )
    if label == "top5" and theme_profile is not None:
      copy = enrich_top5_record_with_theme(copy, theme_profile)
    elif label == "top5":
      terms = ", ".join(f'"{k}"' for k in copy.matched_keywords[:3])
      copy.why_selected = (
        f"include term {terms} 等により Top5 に選抜（読む優先度のみ）"
        if terms
        else "heuristic score により Top5 に選抜（読む優先度のみ）"
      )
    out.append(copy)
  return out


def build_staged_shortlist(
  case_id: str,
  *,
  input_path: Path | str | None = None,
  top100: int = 100,
  top20: int = 20,
  top5: int = 5,
  include_keywords: tuple[str, ...] = (),
  exclude_keywords: tuple[str, ...] = (),
  project_root: Path | str | None = None,
) -> V8LargeCandidateShortlistPack:
  root = Path(project_root or project_root_from_here())
  pinned_top5 = load_top5_publications(case_id, root)
  theme_profile = load_research_theme_profile(case_id, root)
  theme_policy = build_theme_based_ranking_policy(case_id, project_root=root)
  population_path = Path(input_path) if input_path else root / "cases" / case_id / "source_candidates_large.csv"

  population = load_large_candidates_csv(population_path)
  if not population:
    deduped, _ = normalize_and_dedupe_large_candidates(case_id, project_root=root)
  else:
    deduped, _ = normalize_and_dedupe_large_candidates(case_id, project_root=root)
    if not deduped:
      deduped = population

  adapter = score_large_candidates_with_triage(
    deduped,
    case_id=case_id,
    include_keywords=include_keywords,
    exclude_keywords=exclude_keywords,
    project_root=root,
  )
  scored = sorted(
    adapter.scored_records,
    key=lambda r: (-r.heuristic_score, r.publication_number or r.title),
  )
  for rec in scored:
    rec.stage_label = "scored"

  top100_n = min(top100, len(scored))
  top20_n = min(top20, top100_n)
  top5_n = min(top5, top20_n)

  top100_list = _enrich_stage_records(
    scored[:top100_n], label="top100", ranking_policy=adapter.ranking_policy, theme_profile=theme_profile,
  )
  top20_list = _enrich_stage_records(
    scored[:top20_n], label="top20", ranking_policy=adapter.ranking_policy, theme_profile=theme_profile,
  )
  top5_raw = select_top5_preserving_existing(scored, pinned_publications=pinned_top5, top5_n=top5_n)
  top5_list = _enrich_stage_records(
    top5_raw, label="top5", ranking_policy=adapter.ranking_policy, theme_profile=theme_profile,
  )
  dropped_summary = build_dropped_from_top5_summary(top20_list, top5_list, theme_profile)

  stamp = utc_now_iso().replace(":", "").replace("-", "").replace("+00:00", "Z")
  output_dir = get_large_shortlist_dir(case_id, root) / f"pack_{stamp}"
  output_dir.mkdir(parents=True, exist_ok=True)

  pop_copy = [V8LargeCandidateRecord.from_dict(r.to_dict()) for r in population]
  ded_copy = [V8LargeCandidateRecord.from_dict(r.to_dict()) for r in deduped]

  paths = {
    "population": output_dir / "large_candidate_population.csv",
    "deduped": output_dir / "large_candidate_deduped.csv",
    "scored": output_dir / "large_candidate_scored.csv",
    "top100": output_dir / "large_candidate_top100.csv",
    "top20": output_dir / "large_candidate_top20.csv",
    "top5": output_dir / "large_candidate_top5.csv",
    "summary": output_dir / "large_candidate_shortlist_summary.md",
    "manifest": output_dir / "large_candidate_shortlist_manifest.json",
    "ranking_explanation_json": output_dir / "ranking_explanation.json",
    "ranking_explanation_md": output_dir / "ranking_explanation.md",
    "ranking_explanation_csv": output_dir / "ranking_explanation.csv",
    "top5_ranking_explanation": output_dir / "top5_ranking_explanation.md",
    "dropped_candidate_summary": output_dir / "dropped_candidate_summary.md",
  }
  records_to_csv(pop_copy, paths["population"])
  records_to_csv(ded_copy, paths["deduped"])
  records_to_csv(scored, paths["scored"])
  records_to_csv(top100_list, paths["top100"])
  records_to_csv(top20_list, paths["top20"])
  records_to_csv(top5_list, paths["top5"])

  selection = V8LargeCandidateStageSelection(
    selection_id=_selection_id(case_id),
    case_id=case_id,
    generated_at=utc_now_iso(),
    population_count=len(population),
    deduped_count=len(deduped),
    scored_count=len(scored),
    top100_count=len(top100_list),
    top20_count=len(top20_list),
    top5_count=len(top5_list),
    top100_path=str(paths["top100"]),
    top20_path=str(paths["top20"]),
    top5_path=str(paths["top5"]),
    scoring_policy=adapter.ranking_policy,
    ranking_policy=adapter.ranking_policy,
    triage_engine=adapter.triage_engine,
    selection_summary=(
      f"population {len(population)} → deduped {len(deduped)} → "
      f"Top100 {len(top100_list)} → Top20 {len(top20_list)} → Top5 {len(top5_list)}"
    ),
    warnings=list(LARGE_CANDIDATE_SAFETY_NOTICES[:4]) + list(adapter.warnings),
  )

  summary = "\n".join([
    f"# Large Candidate Shortlist Summary — {case_id}",
    "",
    selection.selection_summary,
    "",
    f"- triage_engine: {adapter.triage_engine}",
    f"- ranking_policy: {adapter.ranking_policy}",
    f"- theme_name: {theme_policy.theme_name}",
    f"- top5_pinned: {len(pinned_top5)} publications preserved" if pinned_top5 else "- top5_pinned: (none — score order)",
    f"- top5 deep dive only — Claim Map / Evidence Map は Top5 またはユーザー選択に限定",
    "",
    "## Safety",
    *[f"- {n}" for n in LARGE_CANDIDATE_SAFETY_NOTICES],
  ])
  paths["summary"].write_text(summary, encoding="utf-8")

  ranking_report = build_ranking_explanation_report(
    case_id=case_id,
    population=pop_copy,
    deduped=ded_copy,
    scored=scored,
    top100=top100_list,
    top20=top20_list,
    top5=top5_list,
    ranking_policy=adapter.ranking_policy,
    triage_engine=adapter.triage_engine,
    adapter_result=adapter,
    warnings=adapter.warnings,
  )
  export_ranking_explanation(ranking_report, output_dir)
  (output_dir / "dropped_from_top5_summary.json").write_text(
    json.dumps(dropped_summary.to_dict(), ensure_ascii=False, indent=2),
    encoding="utf-8",
  )
  paths["dropped_candidate_summary"].write_text(
    dropped_summary.summary_text + "\n\n" + ranking_report.dropped_candidate_summary,
    encoding="utf-8",
  )

  manifest = {
    "pack_id": _pack_id(case_id),
    "case_id": case_id,
    "generated_at": selection.generated_at,
    "triage_engine": adapter.triage_engine,
    "ranking_policy": adapter.ranking_policy,
    "theme_ranking_policy": theme_policy.to_dict(),
    "selection": selection.to_dict(),
    "files": {k: str(v) for k, v in paths.items()},
    "safety_notices": list(LARGE_CANDIDATE_SAFETY_NOTICES),
    "ranking_explanation": {
      "report_id": ranking_report.report_id,
      "common_selection_reasons": ranking_report.common_selection_reasons,
      "common_exclusion_reasons": ranking_report.common_exclusion_reasons,
    },
    "dropped_from_top5": dropped_summary.to_dict(),
  }
  paths["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

  return V8LargeCandidateShortlistPack(
    pack_id=manifest["pack_id"],
    case_id=case_id,
    generated_at=selection.generated_at,
    selection=selection,
    population_path=str(paths["population"]),
    deduped_path=str(paths["deduped"]),
    scored_path=str(paths["scored"]),
    summary_path=str(paths["summary"]),
    manifest_path=str(paths["manifest"]),
    output_dir=str(output_dir),
    warnings=list(LARGE_CANDIDATE_SAFETY_NOTICES[:3]) + list(adapter.warnings),
  )


def load_top5_publications(case_id: str, project_root: Path | str | None = None) -> list[str]:
  root = Path(project_root or project_root_from_here())
  latest = find_latest_large_shortlist_dir(case_id, root)
  top5_path = (latest / "large_candidate_top5.csv") if latest else None
  if not top5_path or not top5_path.exists():
    flat = get_large_shortlist_dir(case_id, root) / "large_candidate_top5.csv"
    top5_path = flat if flat.exists() else None
  if not top5_path:
    case_top5 = root / "cases" / case_id / "source_candidates_large_deduped.csv"
    if case_top5.exists():
      recs = load_large_candidates_csv(case_top5)
      recs.sort(key=lambda r: -r.heuristic_score)
      return [r.publication_number for r in recs[:5] if r.publication_number]
    return []
  recs = load_large_candidates_csv(top5_path)
  return [r.publication_number for r in recs if r.publication_number]
