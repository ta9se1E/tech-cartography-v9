"""v8 Large Candidate staged shortlist (Phase 27J.0)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tech_cartography.runtime.v8_large_candidate_schema import (
  CASE_KEYWORDS,
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
from tech_cartography.services.v8_sources_table import project_root_from_here

LOCAL_LARGE_SHORTLIST_SUBDIR = "local_v8_large_shortlists"


def get_large_shortlist_dir(case_id: str, project_root: Path | str | None = None) -> Path:
  root = Path(project_root or project_root_from_here())
  return root / "outputs" / LOCAL_LARGE_SHORTLIST_SUBDIR / case_id


def find_latest_large_shortlist_dir(case_id: str, project_root: Path | str | None = None) -> Path | None:
  base = get_large_shortlist_dir(case_id, project_root)
  if not base.is_dir():
    return None
  dirs = sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
  return dirs[0] if dirs else None


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
  population_path = Path(input_path) if input_path else root / "cases" / case_id / "source_candidates_large.csv"

  population = load_large_candidates_csv(population_path)
  if not population:
    deduped, _ = normalize_and_dedupe_large_candidates(case_id, project_root=root)
  else:
    deduped, _ = normalize_and_dedupe_large_candidates(case_id, project_root=root)
    if not deduped:
      deduped = population

  scored: list[V8LargeCandidateRecord] = []
  for rec in deduped:
    copy = V8LargeCandidateRecord.from_dict(rec.to_dict())
    copy.stage_label = "scored"
    score, reason, matched = score_candidate(
      copy, case_id=case_id, include_keywords=include_keywords, exclude_keywords=exclude_keywords,
    )
    copy.heuristic_score = round(score, 4)
    copy.score_reason = reason
    copy.matched_keywords = matched
    copy.keyword_match_count = len(matched)
    scored.append(copy)

  scored.sort(key=lambda r: (-r.heuristic_score, r.publication_number or r.title))
  top100_n = min(top100, len(scored))
  top20_n = min(top20, top100_n)
  top5_n = min(top5, top20_n)

  def _stage_slice(items: list[V8LargeCandidateRecord], label: str, n: int) -> list[V8LargeCandidateRecord]:
    out: list[V8LargeCandidateRecord] = []
    for rec in items[:n]:
      copy = V8LargeCandidateRecord.from_dict(rec.to_dict())
      copy.stage_label = label
      copy.next_verification_action = (
        f"原典で {copy.publication_number or copy.title[:30]} を人手確認"
        if label == "top5"
        else f"候補スクリーニング: {copy.publication_number or 'no pub'}"
      )
      out.append(copy)
    return out

  top100_list = _stage_slice(scored, "top100", top100_n)
  top20_list = _stage_slice(scored[:top20_n], "top20", top20_n)
  top5_list = _stage_slice(scored[:top5_n], "top5", top5_n)

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
    scoring_policy="keyword_heuristic_v1 — not legal judgement",
    selection_summary=(
      f"population {len(population)} → deduped {len(deduped)} → "
      f"Top100 {len(top100_list)} → Top20 {len(top20_list)} → Top5 {len(top5_list)}"
    ),
    warnings=list(LARGE_CANDIDATE_SAFETY_NOTICES[:4]),
  )

  summary = "\n".join([
    f"# Large Candidate Shortlist Summary — {case_id}",
    "",
    selection.selection_summary,
    "",
    f"- scoring_policy: {selection.scoring_policy}",
    f"- top5 deep dive only — Claim Map / Evidence Map は Top5 またはユーザー選択に限定",
    "",
    "## Safety",
    *[f"- {n}" for n in LARGE_CANDIDATE_SAFETY_NOTICES],
  ])
  paths["summary"].write_text(summary, encoding="utf-8")

  manifest = {
    "pack_id": _pack_id(case_id),
    "case_id": case_id,
    "generated_at": selection.generated_at,
    "selection": selection.to_dict(),
    "files": {k: str(v) for k, v in paths.items()},
    "safety_notices": list(LARGE_CANDIDATE_SAFETY_NOTICES),
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
    warnings=list(LARGE_CANDIDATE_SAFETY_NOTICES[:3]),
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
