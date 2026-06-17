"""Evidence validation report builder."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_evidence_validation_summary(result: dict[str, Any]) -> dict[str, Any]:
  readiness = result.get("fulltext_readiness") or {}
  claim_result = result.get("claim_element_result") or {}
  openalex = result.get("openalex_result") or {}
  paper_evidence = result.get("paper_evidence_result") or {}
  claim_map = result.get("claim_paper_map_result") or {}
  manual_candidates = result.get("manual_candidates") or readiness.get("manual_required_records") or []

  element_types: dict[str, int] = {}
  for element in claim_result.get("elements", []):
    row = element.to_dict() if hasattr(element, "to_dict") else element
    element_type = str(row.get("element_type") or "unknown")
    element_types[element_type] = element_types.get(element_type, 0) + 1

  records_without_claims = [
    {
      "publication_number": row.get("publication_number"),
      "title": row.get("title"),
      "extraction_status": row.get("extraction_status"),
    }
    for row in claim_result.get("record_results", [])
    if row.get("extraction_status") in {"skipped_no_claims", "metadata_only"}
  ]

  claim_only_items = [
    row
    for row in readiness.get("limited_records", [])
    if str(row.get("readiness_status")) == "limited_claim_extraction"
  ]

  supported_by_description = sum(
    1
    for element in claim_result.get("elements", [])
    if (element.to_dict() if hasattr(element, "to_dict") else element).get("supported_by_description")
  )
  supported_by_examples = sum(
    1
    for element in claim_result.get("elements", [])
    if (element.to_dict() if hasattr(element, "to_dict") else element).get("supported_by_examples")
  )

  us_candidates = [
    {
      "publication_number": row.get("publication_number"),
      "title": row.get("title"),
      "retrieval_status": row.get("retrieval_status"),
      "evidence_level": row.get("evidence_level"),
      "readiness_status": row.get("readiness_status"),
      "next_action": _next_action_for_record(row),
    }
    for row in readiness.get("classified_records", [])
    if str(row.get("country") or "US").upper() == "US"
  ]

  evidence_gaps = _build_evidence_gaps(readiness, claim_result, openalex, paper_evidence, claim_map)
  recommended_actions = _build_recommended_actions(readiness, openalex, result.get("status"))
  claims_plan = result.get("claims_paper_query_plan") or {}
  quality_summary = claims_plan.get("quality_summary") or {}
  openalex_limited = result.get("openalex_limited_execution") or {}
  claim_paper_links = result.get("claim_paper_candidate_links") or {}

  return {
    "pipeline_status": result.get("status"),
    "summary": {
      "fulltext_records": readiness.get("total_records", 0),
      "ready_for_claim_extraction": readiness.get("ready_count", 0),
      "limited_extraction": readiness.get("limited_count", 0),
      "dry_run_only": readiness.get("dry_run_only_count", 0),
      "manual_required": readiness.get("manual_required_count", 0),
      "generated_claim_elements": len(claim_result.get("elements", [])),
      "generated_paper_queries": result.get("paper_query_result", {}).get("total_queries", 0),
      "claims_based_paper_queries": claims_plan.get("total_queries", 0),
      "plan_ready_for_openalex": claims_plan.get("plan_ready_for_openalex", False),
      "openalex_mode": openalex_limited.get("mode") or openalex.get("mode", "plan_only"),
      "paper_evidence_links": len(paper_evidence.get("evidence_links", [])),
      "claim_paper_evidence_map_items": len(claim_map.get("evidence_items", [])),
      "openalex_paper_records": openalex_limited.get("total_paper_records", 0),
      "claim_paper_candidate_links": claim_paper_links.get("total_links", 0),
    },
    "fulltext_readiness": readiness,
    "us_candidates": us_candidates,
    "claim_element_extraction": {
      "elements_by_type": element_types,
      "records_without_claims": records_without_claims,
      "claim_only_items": claim_only_items,
      "supported_by_description": supported_by_description,
      "supported_by_examples": supported_by_examples,
    },
    "openalex": {
      "mode": openalex.get("mode", "plan_only"),
      "query_candidates": result.get("paper_query_result", {}).get("total_queries", 0),
      "executed_queries": openalex.get("executed_queries", 0),
      "cache_hits": openalex.get("cache_hits", 0),
      "paper_records": len(openalex.get("papers_dedup", [])),
      "query_plan": openalex.get("query_plan", []),
      "source_quality_count": len(paper_evidence.get("source_quality_results", [])),
    },
    "claims_paper_query_plan": claims_plan,
    "paper_query_quality": quality_summary,
    "manual_watch": {
      "candidates": manual_candidates,
      "count": len(manual_candidates),
    },
    "openalex_limited_execution": openalex_limited,
    "claim_paper_candidate_links": claim_paper_links,
    "evidence_gaps": evidence_gaps,
    "recommended_actions": recommended_actions,
    "warnings": result.get("warnings", []),
    "errors": result.get("errors", []),
    "caveats": [
      "論文 Evidence Candidate は特許主張の証明ではありません。",
      "Full text が取れない特許が重要でないことを意味しません。",
      "中国・EP・JP 等は manual route で継続監視します。",
      "特許有効性・FTO・侵害判断ではありません。",
      "最終判断には専門家レビューが必要です。",
    ],
  }


def _next_action_for_record(record: dict[str, Any]) -> str:
  status = str(record.get("readiness_status") or record.get("retrieval_status") or "")
  if str(record.get("retrieval_status")) in {"manual_claims_loaded", "manual_fulltext_loaded"}:
    return "run-claim-element-extraction"
  if status == "dry_run_only" or str(record.get("retrieval_status")) == "dry_run_only":
    return "execute-fulltext"
  if status == "cost_guard_failed":
    return "execute-fulltext-with-higher-guard-or-manual"
  if status == "ready_for_claim_extraction":
    return "run-claim-element-extraction"
  if status == "limited_claim_extraction":
    return "review-limited-claim-extraction"
  if status == "manual_required":
    return "manual-fulltext-review"
  return "review-metadata"


def _build_evidence_gaps(
  readiness: dict[str, Any],
  claim_result: dict[str, Any],
  openalex: dict[str, Any],
  paper_evidence: dict[str, Any],
  claim_map: dict[str, Any],
) -> list[dict[str, str]]:
  gaps: list[dict[str, str]] = []
  if readiness.get("ready_count", 0) == 0 and readiness.get("limited_count", 0) == 0:
    gaps.append({"gap_type": "no_fulltext", "detail": "No US records with fetched claims/description for extraction."})
  if readiness.get("dry_run_only_count", 0) > 0:
    gaps.append(
      {
        "gap_type": "dry_run_only",
        "detail": f"{readiness.get('dry_run_only_count')} records are dry-run only — まだ請求項を取得していません。",
      },
    )
  if readiness.get("skipped_not_selected_count", 0) > 0:
    gaps.append(
      {
        "gap_type": "skipped_not_selected",
        "detail": f"{readiness.get('skipped_not_selected_count')} records were not selected for execute.",
      },
    )
  if claim_result.get("records_with_claims", 0) == 0 and claim_result.get("total_records", 0) > 0:
    gaps.append({"gap_type": "no_claims", "detail": "Processed records did not yield claims."})
  if not claim_result.get("paper_queries") and not claim_result.get("elements"):
    gaps.append({"gap_type": "no_paper_candidate", "detail": "No paper query candidates were generated."})
  weak_quality = [
    row
    for row in paper_evidence.get("source_quality_results", [])
    if str(row.get("quality_level") or "").lower() in {"weak", "low", "background"}
  ]
  if weak_quality:
    gaps.append(
      {
        "gap_type": "weak_source_quality",
        "detail": f"{len(weak_quality)} paper sources flagged as weak/background.",
      },
    )
  if claim_map.get("evidence_gaps"):
    gaps.append({"gap_type": "claim_paper_gaps", "detail": f"{len(claim_map.get('evidence_gaps', []))} element gaps."})
  return gaps


def _build_recommended_actions(
  readiness: dict[str, Any],
  openalex: dict[str, Any],
  pipeline_status: str | None,
) -> list[str]:
  actions: list[str] = []
  if pipeline_status == "limited_no_fulltext":
    actions.append("まだ請求項を取得していません。--execute-fulltext --fulltext-execute-limit 1 --confirm-fulltext-execute を検討してください")
  elif pipeline_status == "partial_success":
    actions.append("取得できたUS公報のClaim Elementを人間確認してください")
  if readiness.get("ready_count", 0) == 0 and readiness.get("limited_count", 0) == 0:
    if readiness.get("dry_run_only_count", 0) > 0 or readiness.get("cost_guard_failed_count", 0) > 0:
      actions.append("US候補に対して execute-fulltext（Top1から）を実行する")
  if readiness.get("manual_required_count", 0) > 0:
    actions.append("CN/EP/JP 候補は PDF / Google Patents で manual fulltext を追加する")
  if openalex.get("mode") == "plan_only":
    actions.append("必要に応じて OpenAlex を限定実行する（--execute-openalex）")
  if readiness.get("ready_count", 0) > 0 or readiness.get("limited_count", 0) > 0:
    actions.append("Claim Element 抽出結果を人間確認する")
  return actions


def merge_openalex_limited_into_summary(
  summary: dict[str, Any],
  limited: dict[str, Any],
  links: list[dict[str, Any]],
) -> dict[str, Any]:
  merged = dict(summary)
  type_counts: dict[str, int] = {}
  conf_counts: dict[str, int] = {}
  for link in links:
    type_counts[str(link.get("link_type"))] = type_counts.get(str(link.get("link_type")), 0) + 1
    conf_counts[str(link.get("confidence"))] = conf_counts.get(str(link.get("confidence")), 0) + 1

  quality_levels: dict[str, int] = {}
  for row in limited.get("source_quality_results") or []:
    level = str(row.get("quality_level") or "unknown")
    quality_levels[level] = quality_levels.get(level, 0) + 1

  merged["openalex_limited_execution"] = {
    "mode": limited.get("mode", "plan_only"),
    "execution_status": limited.get("execution_status"),
    "executed_queries_count": limited.get("executed_queries_count", 0),
    "skipped_queries_count": limited.get("skipped_queries_count", 0),
    "total_paper_records": limited.get("total_paper_records", 0),
    "cache_hits": limited.get("cache_hits", 0),
    "api_errors": limited.get("api_errors") or [],
    "source_quality_summary": quality_levels,
    "caveat_japanese": limited.get("caveat_japanese"),
    "selected_queries": limited.get("selected_queries") or [],
  }
  merged["claim_paper_candidate_links"] = {
    "total_links": len(links),
    "link_type_distribution": type_counts,
    "confidence_distribution": conf_counts,
    "representative_links": links[:10],
    "caveat_japanese": (
      "これらの論文は、特許請求項を証明するものではなく、"
      "技術背景・材料プロセス・物性関係を確認するための supporting evidence candidate です。"
    ),
  }
  top_summary = dict(merged.get("summary") or {})
  top_summary["openalex_mode"] = limited.get("mode", top_summary.get("openalex_mode", "plan_only"))
  top_summary["openalex_paper_records"] = limited.get("total_paper_records", 0)
  top_summary["claim_paper_candidate_links"] = len(links)
  merged["summary"] = top_summary
  openalex_block = dict(merged.get("openalex") or {})
  openalex_block["mode"] = limited.get("mode", openalex_block.get("mode", "plan_only"))
  openalex_block["executed_queries"] = limited.get("executed_queries_count", 0)
  openalex_block["cache_hits"] = limited.get("cache_hits", 0)
  openalex_block["paper_records"] = limited.get("total_paper_records", 0)
  openalex_block["source_quality_count"] = len(limited.get("source_quality_results") or [])
  merged["openalex"] = openalex_block

  relevance = limited.get("paper_candidate_relevance") or {}
  if relevance:
    all_evaluated = relevance.get("all_evaluated") or []
    selected = relevance.get("selected") or []
    bucket_counts: dict[str, int] = {}
    for row in all_evaluated:
      bucket = str(row.get("relevance_bucket"))
      bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
    excluded = [
      row for row in all_evaluated
      if row.get("relevance_bucket") in {"likely_off_topic", "broad_composite_background"}
    ]
    from tech_cartography.evidence.paper_candidate_relevance_filter import FILTER_CAVEAT_JAPANESE, REPORT_INTRO_JAPANESE

    merged["paper_candidate_relevance"] = {
      "total_paper_candidates": len(all_evaluated),
      "selected_evidence_papers": len(selected),
      "relevance_bucket_distribution": bucket_counts,
      "representative_selected_papers": selected[:5],
      "excluded_broad_off_topic": excluded[:10],
      "excluded_off_topic_count": relevance.get("excluded_off_topic_count", 0),
      "broad_background_count": relevance.get("broad_background_count", 0),
      "caveat_japanese": FILTER_CAVEAT_JAPANESE,
      "intro_japanese": REPORT_INTRO_JAPANESE,
    }
    top_summary["selected_evidence_papers"] = len(selected)
    merged["summary"] = top_summary

  return merged


def patch_evidence_validation_with_openalex_limited(
  evidence_dir: str | Path,
  limited: dict[str, Any],
  links: list[dict[str, Any]],
) -> dict[str, str]:
  out = Path(evidence_dir)
  summary_path = out / "evidence_validation_summary.json"
  report_path = out / "evidence_validation_report.md"
  if not summary_path.exists():
    return {}
  summary = json.loads(summary_path.read_text(encoding="utf-8"))
  merged = merge_openalex_limited_into_summary(summary, limited, links)
  summary_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
  report_path.write_text(render_evidence_validation_markdown(merged), encoding="utf-8")
  return {
    "evidence_validation_summary_json": str(summary_path),
    "evidence_validation_report_md": str(report_path),
  }


def _render_openalex_limited_sections(summary: dict[str, Any]) -> list[str]:
  limited = summary.get("openalex_limited_execution") or {}
  if not limited:
    return []
  lines = [
    "## OpenAlex Limited Execution",
    "",
    f"- 実行モード: {limited.get('mode', 'plan_only')}",
    f"- execution status: {limited.get('execution_status', 'plan_only')}",
    f"- 実行query数: {limited.get('executed_queries_count', 0)}",
    f"- skipped queries: {limited.get('skipped_queries_count', 0)}",
    f"- 取得paper数: {limited.get('total_paper_records', 0)}",
    f"- cache hits: {limited.get('cache_hits', 0)}",
  ]
  errors = limited.get("api_errors") or []
  if errors:
    lines.append(f"- API errors: {len(errors)}")
    for err in errors[:5]:
      lines.append(f"  - {err}")
  else:
    lines.append("- API errors: 0")

  quality = limited.get("source_quality_summary") or {}
  lines.extend(["", "### source quality summary", ""])
  if quality:
    for level, count in sorted(quality.items()):
      lines.append(f"- {level}: {count}")
  else:
    lines.append("- (no source quality evaluations)")

  lines.extend(["", "### selected queries", ""])
  for row in limited.get("selected_queries") or []:
    lines.append(f"- [{row.get('query_type')}] ({row.get('confidence')}) {row.get('query')}")
  if not limited.get("selected_queries"):
    lines.append("- (none)")

  lines.extend(
    [
      "",
      "### caveat",
      "",
      limited.get("caveat_japanese")
      or "これらの論文は、特許請求項を証明するものではなく、技術背景・材料プロセス・物性関係を確認するための supporting evidence candidate です。",
      "",
      "これらの論文は、特許請求項を証明するものではなく、技術背景・材料プロセス・物性関係を確認するための supporting evidence candidate です。",
      "",
    ],
  )
  return lines


def _render_claim_paper_candidate_sections(summary: dict[str, Any]) -> list[str]:
  block = summary.get("claim_paper_candidate_links") or {}
  if not block.get("total_links") and not block.get("representative_links"):
    return []
  lines = [
    "## Claim × Paper Candidate Links",
    "",
    f"- link数: {block.get('total_links', 0)}",
    "",
    "### link_type分布",
    "",
  ]
  for key, count in sorted((block.get("link_type_distribution") or {}).items()):
    lines.append(f"- {key}: {count}")
  lines.extend(["", "### confidence分布", ""])
  for key, count in sorted((block.get("confidence_distribution") or {}).items()):
    lines.append(f"- {key}: {count}")
  lines.extend(["", "### 代表リンク", ""])
  for link in block.get("representative_links") or []:
    lines.append(
      f"- {link.get('element_type')} ↔ {link.get('paper_title')} "
      f"({link.get('link_type')}, {link.get('confidence')})",
    )
  if not block.get("representative_links"):
    lines.append("- (no links)")
  lines.extend(["", block.get("caveat_japanese", ""), ""])
  return lines


def _render_paper_candidate_relevance_sections(summary: dict[str, Any]) -> list[str]:
  block = summary.get("paper_candidate_relevance") or {}
  if not block:
    return []
  lines = [
    "## Paper Candidate Relevance Filter",
    "",
    block.get("intro_japanese")
    or "広い複合材料レビューは背景候補として扱い、PAN系炭素繊維・炭化・物性に近い論文をEvidence Map候補として優先します。",
    "",
    f"- total paper candidates: {block.get('total_paper_candidates', 0)}",
    f"- selected evidence papers: {block.get('selected_evidence_papers', 0)}",
    f"- excluded off-topic: {block.get('excluded_off_topic_count', 0)}",
    f"- broad background: {block.get('broad_background_count', 0)}",
    "",
    "### relevance bucket distribution",
    "",
  ]
  for key, count in sorted((block.get("relevance_bucket_distribution") or {}).items()):
    lines.append(f"- {key}: {count}")
  lines.extend(["", "### representative selected papers", ""])
  for row in block.get("representative_selected_papers") or []:
    lines.append(
      f"- {row.get('title')} ({row.get('relevance_bucket')}, score={row.get('relevance_score')})",
    )
  if not block.get("representative_selected_papers"):
    lines.append("- (none)")
  lines.extend(["", "### excluded broad/off-topic papers", ""])
  for row in block.get("excluded_broad_off_topic") or []:
    lines.append(f"- {row.get('title')} ({row.get('relevance_bucket')})")
  if not block.get("excluded_broad_off_topic"):
    lines.append("- (none)")
  lines.extend(["", "### caveat", "", block.get("caveat_japanese", ""), ""])
  return lines


def render_evidence_validation_markdown(summary: dict[str, Any]) -> str:
  s = summary.get("summary") or {}
  lines = [
    "# Evidence Validation Report",
    "",
    "## 1. Summary",
    "",
    f"- fulltext records: {s.get('fulltext_records', 0)}",
    f"- ready for claim extraction: {s.get('ready_for_claim_extraction', 0)}",
    f"- limited extraction: {s.get('limited_extraction', 0)}",
    f"- dry-run only: {s.get('dry_run_only', 0)}",
    f"- manual required: {s.get('manual_required', 0)}",
    f"- generated claim elements: {s.get('generated_claim_elements', 0)}",
    f"- generated paper queries: {s.get('generated_paper_queries', 0)}",
    f"- OpenAlex mode: {s.get('openalex_mode', 'plan_only')}",
    f"- paper evidence links: {s.get('paper_evidence_links', 0)}",
    f"- claim paper evidence map items: {s.get('claim_paper_evidence_map_items', 0)}",
    f"- pipeline status: {summary.get('pipeline_status')}",
    "",
    "claims_only 取得の場合は「請求項ベースの限定検証」として Claim Element Extraction を進めます。",
    "明細書がなくても請求項から paper query 候補を生成できます。",
    "",
    "## 2. Full Text Readiness",
    "",
    "### US候補",
    "",
  ]

  for row in summary.get("us_candidates", []):
    lines.append(
      f"- {row.get('publication_number')}: {row.get('title')} | "
      f"retrieval={row.get('retrieval_status')} | evidence={row.get('evidence_level')} | "
      f"next={row.get('next_action')}",
    )
  manual_loaded = [
    row
    for row in summary.get("us_candidates", [])
    if str(row.get("retrieval_status") or "") in {"manual_claims_loaded", "manual_fulltext_loaded"}
  ]
  if manual_loaded:
    lines.extend(["", "### Manual Route（成功）", ""])
    for row in manual_loaded:
      lines.append(
        f"- {row.get('publication_number')}: manual fulltext route loaded → claim extraction ready",
      )
  if not summary.get("us_candidates"):
    lines.append("- (no US fulltext records)")

  claim_section = summary.get("claim_element_extraction") or {}
  lines.extend(
    [
      "",
      "## 3. Claim Element Extraction Result",
      "",
      "### extracted elements by type",
      "",
    ],
  )
  for element_type, count in (claim_section.get("elements_by_type") or {}).items():
    lines.append(f"- {element_type}: {count}")
  if not claim_section.get("elements_by_type"):
    lines.append("- (none)")

  lines.extend(
    [
      "",
      f"- records without claims: {len(claim_section.get('records_without_claims', []))}",
      f"- claim_only items: {len(claim_section.get('claim_only_items', []))}",
      f"- supported_by_description: {claim_section.get('supported_by_description', 0)}",
      f"- supported_by_examples: {claim_section.get('supported_by_examples', 0)}",
      "",
      "## 4. OpenAlex Paper Evidence Plan / Result",
      "",
    ],
  )
  openalex = summary.get("openalex") or {}
  lines.extend(
    [
      f"- query candidates: {openalex.get('query_candidates', 0)}",
      f"- executed queries: {openalex.get('executed_queries', 0)}",
      f"- cache hits: {openalex.get('cache_hits', 0)}",
      f"- paper records: {openalex.get('paper_records', 0)}",
      f"- source quality evaluations: {openalex.get('source_quality_count', 0)}",
      "",
      "## Claims-based Paper Query Plan",
      "",
    ],
  )
  claims_plan = summary.get("claims_paper_query_plan") or {}
  quality = summary.get("paper_query_quality") or claims_plan.get("quality_summary") or {}
  lines.extend(
    [
      f"- manual claimsから生成したquery数: {claims_plan.get('total_queries', 0)}",
      f"- OpenAlex mode: {claims_plan.get('openalex_mode', 'plan_only')}",
      f"- confidence: {', '.join(claims_plan.get('confidence_levels', [])) or 'n/a'}",
      f"- plan ready for OpenAlex: {claims_plan.get('plan_ready_for_openalex', quality.get('plan_ready_for_openalex', False))}",
      "",
      "この段階では、請求項とメタデータから生成した論文検索候補です。明細書・実施例が未入力のため、数値条件や測定方法の裏取りは限定的です。",
      "",
      "### query_type distribution",
      "",
    ],
  )
  for qtype, count in sorted((claims_plan.get("query_type_distribution") or quality.get("query_type_distribution") or {}).items()):
    lines.append(f"- {qtype}: {count}")
  lines.extend(["", "### confidence distribution", ""])
  for conf, count in sorted((claims_plan.get("confidence_distribution") or quality.get("confidence_distribution") or {}).items()):
    lines.append(f"- {conf}: {count}")
  lines.extend(["", "### query examples", ""])
  for example in claims_plan.get("query_examples", []):
    lines.append(f"- {example}")
  if not claims_plan.get("query_examples"):
    for row in (claims_plan.get("queries") or [])[:5]:
      lines.append(f"- {row.get('query')}")
  if not claims_plan.get("queries"):
    lines.append("- (no claims-based queries)")
  lines.extend(["", "### caveat", "", claims_plan.get("caveat_japanese") or "", ""])

  openalex_sections = _render_openalex_limited_sections(summary)
  if openalex_sections:
    lines.extend(openalex_sections)
  claim_link_sections = _render_claim_paper_candidate_sections(summary)
  if claim_link_sections:
    lines.extend(claim_link_sections)
  relevance_sections = _render_paper_candidate_relevance_sections(summary)
  if relevance_sections:
    lines.extend(relevance_sections)

  lines.extend(["## 5. China / Non-US Manual Watch", ""])
  manual = summary.get("manual_watch") or {}
  for row in manual.get("candidates", []):
    pub = row.get("publication_number")
    country = row.get("country")
    title = row.get("title")
    assignee = row.get("assignee")
    lines.append(f"- {pub} ({country}): {title} | {assignee}")
  if not manual.get("candidates"):
    lines.append("- (no manual watch candidates in this run)")

  lines.extend(["", "## 6. Evidence Gaps", ""])
  for gap in summary.get("evidence_gaps", []):
    lines.append(f"- {gap.get('gap_type')}: {gap.get('detail')}")
  if not summary.get("evidence_gaps"):
    lines.append("- (none identified)")

  lines.extend(["", "## 7. Recommended Next Actions", ""])
  for action in summary.get("recommended_actions", []):
    lines.append(f"- {action}")
  for action_row in (summary.get("fulltext_readiness") or {}).get("next_actions", []):
    lines.append(f"- {action_row.get('action_id')}: {action_row.get('reason')}")

  lines.extend(["", "## 8. Caveats", ""])
  for caveat in summary.get("caveats", []):
    lines.append(f"- {caveat}")

  if summary.get("warnings"):
    lines.extend(["", "## Warnings", ""])
    for warning in summary.get("warnings", []):
      lines.append(f"- {warning}")

  return "\n".join(lines)


def save_evidence_validation_report(markdown: str, output_dir: str | Path) -> str:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  path = out / "evidence_validation_report.md"
  path.write_text(markdown, encoding="utf-8")
  return str(path)
