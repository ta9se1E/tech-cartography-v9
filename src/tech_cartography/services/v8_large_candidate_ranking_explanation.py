"""v8 Large Candidate ranking explanation service (Phase 27J.1)."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tech_cartography.runtime.v8_large_candidate_schema import V8LargeCandidateRecord
from tech_cartography.runtime.v8_ranking_explanation_schema import (
  RANKING_EXPLANATION_NOTICES,
  V8CandidateRankingExplanation,
  V8RankingExplanationExport,
  V8RankingExplanationReport,
  V8ScoreContribution,
  V8StageRankingExplanation,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_large_candidate_import import load_large_candidates_csv

if TYPE_CHECKING:
  from tech_cartography.services.v8_patent_triage_adapter import V8PatentTriageAdapterResult


def _report_id(case_id: str) -> str:
  digest = hashlib.sha256(f"{case_id}|ranking|{utc_now_iso()}".encode()).hexdigest()[:12]
  return f"{case_id}:ranking_explanation:{digest}"


def _contrib_id(candidate_id: str, factor: str, idx: int) -> str:
  return f"{candidate_id}:contrib:{factor}:{idx}"


def _build_contributions_from_record(rec: V8LargeCandidateRecord, adapter: Any | None) -> list[V8ScoreContribution]:
  contribs: list[V8ScoreContribution] = []
  if adapter and adapter.triage_results:
    idx_map = {r.candidate_id: r for r in adapter.scored_records}
    triage_idx = {getattr(t, "candidate_id", ""): t for t in adapter.triage_results}
    triage = triage_idx.get(rec.candidate_id)
    if triage and hasattr(triage, "contributions"):
      for i, c in enumerate(triage.contributions):
        contribs.append(V8ScoreContribution(
          contribution_id=_contrib_id(rec.candidate_id, c.factor_name, i),
          factor_name=c.factor_name,
          matched_value=c.matched_value,
          score_delta=c.score_delta,
          reason=c.reason,
          evidence_field=c.evidence_field,
        ))
      return contribs

  # Parse score_reason / matched_keywords for fallback
  for i, kw in enumerate(rec.matched_keywords):
    contribs.append(V8ScoreContribution(
      contribution_id=_contrib_id(rec.candidate_id, "include_term_hit", i),
      factor_name="include_term_hit" if "exclude" not in kw else "exclude_term_hit",
      matched_value=kw,
      score_delta=0.12,
      reason=f'keyword "{kw}" matched',
      evidence_field="title/abstract/organization",
    ))
  for i, part in enumerate(rec.positive_reasons):
    contribs.append(V8ScoreContribution(
      contribution_id=_contrib_id(rec.candidate_id, "fallback_heuristic", i),
      factor_name="fallback_heuristic" if "fallback" in rec.ranking_policy else "unknown",
      matched_value=part,
      score_delta=0.0,
      reason=part,
      evidence_field="heuristic",
    ))
  for i, part in enumerate(rec.negative_reasons):
    contribs.append(V8ScoreContribution(
      contribution_id=_contrib_id(rec.candidate_id, "quality_penalty", i),
      factor_name="quality_penalty" if "penalty" in part else "exclude_term_hit",
      matched_value=part,
      score_delta=-0.2,
      reason=part,
      evidence_field="quality",
    ))
  return contribs


def _why_selected_text(rec: V8LargeCandidateRecord, case_id: str) -> str:
  terms = ", ".join(f'"{k}"' for k in rec.matched_keywords[:4])
  parts = []
  if terms:
    parts.append(f"Case {case_id} の include term {terms} に一致したため加点されました。")
  if rec.publication_number and rec.title and rec.abstract:
    parts.append("publication_number / title / abstract が揃っているため品質加点されました。")
  if rec.country_code.upper() == "US" or rec.publication_number.upper().startswith("US"):
    parts.append("US公報のため加点されました。")
  parts.append("これは読む優先度の暫定スコアであり、技術的妥当性や特許価値を示すものではありません。")
  return " ".join(parts) if parts else "heuristic score により段階選抜に残りました（読む優先度のみ）。"


def _why_not_selected_text(rec: V8LargeCandidateRecord, better: V8LargeCandidateRecord) -> str:
  if rec.heuristic_score < better.heuristic_score:
    return (
      f"Top5には入りませんでした。heuristic_score {rec.heuristic_score} は "
      f"Top5最下位 {better.heuristic_score} より低く、"
      f"include term 一致数 {rec.keyword_match_count} < {better.keyword_match_count} のためです。"
    )
  return "段階選抜の定員により除外されました（スコアは読む優先度のみ）。"


def build_ranking_explanation_report(
  *,
  case_id: str,
  population: list[V8LargeCandidateRecord],
  deduped: list[V8LargeCandidateRecord],
  scored: list[V8LargeCandidateRecord],
  top100: list[V8LargeCandidateRecord],
  top20: list[V8LargeCandidateRecord],
  top5: list[V8LargeCandidateRecord],
  ranking_policy: str,
  triage_engine: str,
  adapter_result: Any | None = None,
  warnings: list[str] | None = None,
) -> V8RankingExplanationReport:
  top5_ids = {r.candidate_id for r in top5}
  top20_ids = {r.candidate_id for r in top20}
  top100_ids = {r.candidate_id for r in top100}
  scored_rank = {r.candidate_id: i + 1 for i, r in enumerate(sorted(scored, key=lambda x: -x.heuristic_score))}
  deduped_rank = {r.candidate_id: i + 1 for i, r in enumerate(deduped)}
  pop_rank = {r.candidate_id: i + 1 for i, r in enumerate(population)}

  stage_explanations = [
    V8StageRankingExplanation(
      stage_name="population",
      input_count=len(population),
      output_count=len(population),
      selection_rule="CSV/Excel import — max 1000 rows, no external API",
      warnings=["母集団 — 全件 Deep Dive 対象ではない"],
    ),
    V8StageRankingExplanation(
      stage_name="deduped",
      input_count=len(population),
      output_count=len(deduped),
      selection_rule="暫定 dedupe: publication_number / family_id / title similarity",
      main_negative_factors=["duplicate publication_number", "duplicate family_id", "near-duplicate title"],
      warnings=["family_id や title 類似だけで同一特許と断定しない"],
    ),
    V8StageRankingExplanation(
      stage_name="scored",
      input_count=len(deduped),
      output_count=len(scored),
      selection_rule=f"scoring via {triage_engine}",
      main_positive_factors=["include_term_hit", "target_company_hit", "us_publication", "title/abstract present"],
      main_negative_factors=["exclude_term_hit", "quality_penalty"],
    ),
    V8StageRankingExplanation(
      stage_name="top100",
      input_count=len(scored),
      output_count=len(top100),
      selection_rule="heuristic_score 降順で上位100件",
    ),
    V8StageRankingExplanation(
      stage_name="top20",
      input_count=len(top100),
      output_count=len(top20),
      selection_rule="Top100 から上位20件",
    ),
    V8StageRankingExplanation(
      stage_name="top5",
      input_count=len(top20),
      output_count=len(top5),
      selection_rule="Top20 から上位5件 — Claim Map / Evidence Map Deep Dive 対象",
    ),
  ]

  candidate_explanations: list[V8CandidateRankingExplanation] = []
  focus_ids = top100_ids | {r.candidate_id for r in deduped if r.is_duplicate}
  scored_map = {r.candidate_id: r for r in scored}
  bottom_top5 = top5[-1] if top5 else None

  for cid in focus_ids:
    rec = scored_map.get(cid) or next((r for r in deduped + population if r.candidate_id == cid), None)
    if not rec:
      continue
    in_top5 = cid in top5_ids
    in_top20 = cid in top20_ids
    in_top100 = cid in top100_ids
    why_not = ""
    if in_top20 and not in_top5 and bottom_top5:
      why_not = _why_not_selected_text(rec, bottom_top5)
    elif in_top100 and not in_top20 and top20:
      why_not = _why_not_selected_text(rec, top20[-1])
    candidate_explanations.append(V8CandidateRankingExplanation(
      candidate_id=rec.candidate_id,
      case_id=case_id,
      publication_number=rec.publication_number,
      title=rec.title,
      organization=rec.organization,
      assignee=rec.assignee,
      year=rec.year,
      country_code=rec.country_code,
      stage_label=rec.stage_label,
      heuristic_score=rec.heuristic_score,
      rank_in_population=pop_rank.get(cid, 0),
      rank_in_deduped=deduped_rank.get(cid, 0),
      rank_in_scored=scored_rank.get(cid, 0),
      rank_in_top100=next((i + 1 for i, r in enumerate(top100) if r.candidate_id == cid), 0),
      rank_in_top20=next((i + 1 for i, r in enumerate(top20) if r.candidate_id == cid), 0),
      rank_in_top5=next((i + 1 for i, r in enumerate(top5) if r.candidate_id == cid), 0),
      selected_for_top100=in_top100,
      selected_for_top20=in_top20,
      selected_for_top5=in_top5,
      selected_for_deep_dive=in_top5,
      score_contributions=_build_contributions_from_record(rec, adapter_result),
      positive_reasons=list(rec.positive_reasons),
      negative_reasons=list(rec.negative_reasons),
      why_selected=_why_selected_text(rec, case_id) if in_top5 else "",
      why_not_selected=why_not,
      next_verification_action=rec.next_verification_action,
      ranking_policy=ranking_policy,
      caution_flags=["reading_priority_only", "no_legal_judgement"],
    ))

  pos_counter: Counter[str] = Counter()
  neg_counter: Counter[str] = Counter()
  for rec in top5:
    for p in rec.positive_reasons:
      pos_counter[p.split('"')[1] if '"' in p else p] += 1
    for n in rec.negative_reasons:
      neg_counter[n] += 1

  top5_lines = [
    f"## Top5 summary — {case_id}",
    "",
    f"ranking_policy: {ranking_policy}",
    f"triage_engine: {triage_engine}",
    "",
  ]
  for i, rec in enumerate(top5, 1):
    top5_lines.append(f"### #{i} {rec.publication_number} — {rec.title[:60]}")
    top5_lines.append(f"- score: {rec.heuristic_score}")
    top5_lines.append(f"- why: {_why_selected_text(rec, case_id)}")
    top5_lines.append(f"- positive: {', '.join(rec.positive_reasons[:5])}")
    top5_lines.append(f"- negative: {', '.join(rec.negative_reasons[:3]) or '（なし）'}")
    top5_lines.append("")

  dropped_lines = [
    f"## Dropped from Top5 (Top20 holdovers) — {case_id}",
    "",
  ]
  for rec in top20:
    if rec.candidate_id in top5_ids:
      continue
    dropped_lines.append(f"- {rec.publication_number}: {_why_not_selected_text(rec, top5[-1]) if top5 else 'rank cutoff'}")

  return V8RankingExplanationReport(
    report_id=_report_id(case_id),
    case_id=case_id,
    generated_at=utc_now_iso(),
    ranking_policy=ranking_policy,
    triage_engine=triage_engine,
    population_count=len(population),
    deduped_count=len(deduped),
    scored_count=len(scored),
    top100_count=len(top100),
    top20_count=len(top20),
    top5_count=len(top5),
    stage_explanations=stage_explanations,
    candidate_explanations=candidate_explanations,
    top5_summary="\n".join(top5_lines),
    dropped_candidate_summary="\n".join(dropped_lines),
    common_selection_reasons=[f"{k} ({v})" for k, v in pos_counter.most_common(5)],
    common_exclusion_reasons=[f"{k} ({v})" for k, v in neg_counter.most_common(5)],
    warnings=list(warnings or []) + list(RANKING_EXPLANATION_NOTICES[:2]),
  )


def export_ranking_explanation(
  report: V8RankingExplanationReport,
  output_dir: Path | str,
) -> V8RankingExplanationExport:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  json_path = out / "ranking_explanation.json"
  md_path = out / "ranking_explanation.md"
  csv_path = out / "ranking_explanation.csv"
  top5_md = out / "top5_ranking_explanation.md"
  dropped_md = out / "dropped_candidate_summary.md"

  json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

  md_lines = [
    f"# Ranking Explanation — {report.case_id}",
    "",
    f"- generated_at: {report.generated_at}",
    f"- triage_engine: {report.triage_engine}",
    f"- ranking_policy: {report.ranking_policy}",
    "",
    "## Funnel",
    f"- population: {report.population_count}",
    f"- deduped: {report.deduped_count}",
    f"- scored: {report.scored_count}",
    f"- Top100: {report.top100_count}",
    f"- Top20: {report.top20_count}",
    f"- Top5: {report.top5_count}",
    "",
    "## Common selection reasons",
    *[f"- {r}" for r in report.common_selection_reasons],
    "",
    "## Common exclusion reasons",
    *[f"- {r}" for r in report.common_exclusion_reasons],
    "",
    "## Safety",
    *[f"- {n}" for n in RANKING_EXPLANATION_NOTICES],
  ]
  md_path.write_text("\n".join(md_lines), encoding="utf-8")
  top5_md.write_text(report.top5_summary, encoding="utf-8")
  dropped_md.write_text(report.dropped_candidate_summary, encoding="utf-8")

  fieldnames = [
    "candidate_id", "publication_number", "title", "heuristic_score", "stage_label",
    "selected_for_top5", "why_selected", "why_not_selected",
    "positive_reasons", "negative_reasons", "ranking_policy",
  ]
  with csv_path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    for c in report.candidate_explanations:
      writer.writerow({
        "candidate_id": c.candidate_id,
        "publication_number": c.publication_number,
        "title": c.title[:120],
        "heuristic_score": c.heuristic_score,
        "stage_label": c.stage_label,
        "selected_for_top5": c.selected_for_top5,
        "why_selected": c.why_selected,
        "why_not_selected": c.why_not_selected,
        "positive_reasons": "|".join(c.positive_reasons),
        "negative_reasons": "|".join(c.negative_reasons),
        "ranking_policy": c.ranking_policy,
      })

  return V8RankingExplanationExport(
    export_id=report.report_id,
    case_id=report.case_id,
    output_dir=str(out),
    json_path=str(json_path),
    md_path=str(md_path),
    csv_path=str(csv_path),
    top5_md_path=str(top5_md),
    dropped_md_path=str(dropped_md),
  )


def build_ranking_explanation_from_pack_dir(
  case_id: str,
  pack_dir: Path | str,
  *,
  adapter_result: Any | None = None,
  ranking_policy: str = "",
  triage_engine: str = "fallback_large_candidate_heuristic",
) -> V8RankingExplanationExport:
  pack = Path(pack_dir)
  population = load_large_candidates_csv(pack / "large_candidate_population.csv")
  deduped = load_large_candidates_csv(pack / "large_candidate_deduped.csv")
  scored = load_large_candidates_csv(pack / "large_candidate_scored.csv")
  top100 = load_large_candidates_csv(pack / "large_candidate_top100.csv")
  top20 = load_large_candidates_csv(pack / "large_candidate_top20.csv")
  top5 = load_large_candidates_csv(pack / "large_candidate_top5.csv")

  manifest_path = pack / "large_candidate_shortlist_manifest.json"
  if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ranking_policy = ranking_policy or manifest.get("ranking_policy") or manifest.get("selection", {}).get("scoring_policy", "")
    triage_engine = triage_engine or manifest.get("triage_engine", triage_engine)

  report = build_ranking_explanation_report(
    case_id=case_id,
    population=population,
    deduped=deduped,
    scored=scored,
    top100=top100,
    top20=top20,
    top5=top5,
    ranking_policy=ranking_policy,
    triage_engine=triage_engine,
    adapter_result=adapter_result,
  )
  return export_ranking_explanation(report, pack)
