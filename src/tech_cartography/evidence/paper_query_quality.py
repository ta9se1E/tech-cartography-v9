"""Quality evaluation for claims-based paper query candidates."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def evaluate_paper_query_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
  query = str(candidate.get("query") or "").strip()
  query_type = str(candidate.get("query_type") or "broad_background")
  confidence = str(candidate.get("confidence") or "low")
  word_count = len(query.split())
  is_empty = not query
  is_broad = query_type == "broad_background" or word_count <= 3
  return {
    "query_id": candidate.get("query_id"),
    "query": query,
    "query_type": query_type,
    "confidence": confidence,
    "is_empty": is_empty,
    "is_broad": is_broad,
    "word_count": word_count,
    "quality_score": float(candidate.get("quality_score", 0)),
  }


def evaluate_paper_query_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
  rows = [evaluate_paper_query_candidate(row) for row in candidates]
  types = [str(row.get("query_type") or "") for row in candidates]
  type_distribution = dict(Counter(types))
  confidences = [str(row.get("confidence") or "low") for row in candidates]
  confidence_distribution = dict(Counter(confidences))

  normalized_keys: list[str] = []
  duplicate_count = 0
  seen: set[str] = set()
  for row in candidates:
    key = " ".join(str(row.get("query") or "").lower().split())
    if not key:
      continue
    if key in seen:
      duplicate_count += 1
    else:
      seen.add(key)
      normalized_keys.append(key)

  has_material_process = any(t in types for t in ("material_process", "process_condition"))
  has_property = any(t in types for t in ("property_condition", "structure_property"))
  has_structure_property = "structure_property" in types
  has_surface_interface = "surface_interface" in types
  has_broad_background = "broad_background" in types
  only_broad = bool(types) and all(t == "broad_background" for t in types)
  empty_count = sum(1 for row in rows if row["is_empty"])

  query_count = len([row for row in candidates if str(row.get("query") or "").strip()])
  plan_ready_for_openalex = (
    query_count >= 5
    and has_material_process
    and has_property
    and not only_broad
    and empty_count == 0
  )

  return {
    "query_count": query_count,
    "duplicate_count": duplicate_count,
    "has_material_process_query": has_material_process,
    "has_property_query": has_property,
    "has_structure_property_query": has_structure_property,
    "has_surface_interface_query": has_surface_interface,
    "has_broad_background_query": has_broad_background,
    "only_broad_background": only_broad,
    "empty_query_count": empty_count,
    "query_type_distribution": type_distribution,
    "confidence_distribution": confidence_distribution,
    "plan_ready_for_openalex": plan_ready_for_openalex,
    "openalex_mode": "plan_only",
    "caveat_japanese": (
      "この段階では、請求項とメタデータから生成した論文検索候補です。"
      "明細書・実施例が未入力のため、数値条件や測定方法の裏取りは限定的です。"
      "論文は証明ではなく supporting evidence candidate です。"
    ),
    "next_actions_japanese": [
      "descriptionを追加する",
      "OpenAlexを限定実行する",
      "技術者がquery妥当性を確認する",
    ],
  }


def render_paper_query_quality_report(
  candidates: list[dict[str, Any]],
  summary: dict[str, Any] | None = None,
) -> str:
  quality = summary or evaluate_paper_query_candidates(candidates)
  lines = [
    "# Paper Query Quality Report",
    "",
    f"- query count: {quality.get('query_count', 0)}",
    f"- duplicate count: {quality.get('duplicate_count', 0)}",
    f"- plan ready for OpenAlex: {quality.get('plan_ready_for_openalex', False)}",
    f"- OpenAlex mode: {quality.get('openalex_mode', 'plan_only')}",
    "",
    "## Coverage",
    "",
    f"- material/process query: {quality.get('has_material_process_query', False)}",
    f"- property query: {quality.get('has_property_query', False)}",
    f"- structure-property query: {quality.get('has_structure_property_query', False)}",
    f"- surface/interface query: {quality.get('has_surface_interface_query', False)}",
    f"- broad background query: {quality.get('has_broad_background_query', False)}",
    "",
    "## query_type distribution",
    "",
  ]
  for qtype, count in sorted((quality.get("query_type_distribution") or {}).items()):
    lines.append(f"- {qtype}: {count}")
  lines.extend(["", "## confidence distribution", ""])
  for conf, count in sorted((quality.get("confidence_distribution") or {}).items()):
    lines.append(f"- {conf}: {count}")

  lines.extend(["", "## Representative queries", ""])
  for row in candidates[:5]:
    lines.append(
      f"- [{row.get('query_type')}] ({row.get('confidence')}) {row.get('query')}",
    )
  if not candidates:
    lines.append("- (none)")

  lines.extend(["", "## Caveat", "", quality.get("caveat_japanese") or "", ""])
  lines.append("※ 金額・課金情報は含みません。")
  return "\n".join(lines)


def save_paper_query_quality_artifacts(
  candidates: list[dict[str, Any]],
  output_dir: str | Path,
  *,
  summary: dict[str, Any] | None = None,
) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  quality = summary or evaluate_paper_query_candidates(candidates)
  json_path = out / "paper_query_quality_summary.json"
  md_path = out / "paper_query_quality_report.md"
  json_path.write_text(json.dumps(quality, indent=2, ensure_ascii=False), encoding="utf-8")
  md_path.write_text(render_paper_query_quality_report(candidates, quality), encoding="utf-8")
  return {
    "paper_query_quality_summary_json": str(json_path),
    "paper_query_quality_report_md": str(md_path),
  }
