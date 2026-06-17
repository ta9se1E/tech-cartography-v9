"""Evidence Map synthesis report builder (Phase 20)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.evidence.evidence_map_synthesizer import EvidenceMapSynthesis, SYNTHESIS_CAVEAT
from tech_cartography.reports.project_export import save_records_csv


def render_evidence_map_synthesis_markdown(synthesis: EvidenceMapSynthesis | dict[str, Any]) -> str:
  if isinstance(synthesis, EvidenceMapSynthesis):
    data = synthesis.to_dict()
  else:
    data = synthesis

  lines = [
    "# Evidence Map Synthesis",
    "",
    "## 対象特許",
    "",
    f"- publication number: {data.get('publication_number', '')}",
    f"- title: {data.get('title', '')}",
    f"- assignee: {data.get('assignee', '') or '(unknown)'}",
    f"- retrieval route: {data.get('retrieval_route', '')}",
    f"- evidence level: {data.get('evidence_level', '')}",
    f"- synthesis status: {data.get('synthesis_status', '')}",
    "",
    SYNTHESIS_CAVEAT,
    "",
    "## 1. この特許で読めたこと",
    "",
    f"- Claim Element数: {data.get('claim_element_count', 0)}",
    f"- paper query候補数: {data.get('paper_query_count', 0)}",
    "",
    "### extracted elements by type",
    "",
  ]
  for etype, count in sorted((data.get("element_type_counts") or {}).items()):
    lines.append(f"- {etype}: {count}")
  if not data.get("element_type_counts"):
    lines.append("- (none)")

  for finding in data.get("key_findings_japanese") or []:
    lines.append(f"- {finding}")

  lines.extend(
    [
      "",
      "## 2. 論文裏取り候補",
      "",
      f"- OpenAlex candidate count: {data.get('paper_candidate_count', 0)}",
      f"- selected evidence papers: {data.get('selected_evidence_paper_count', 0)}",
      "",
      "### representative selected papers (supporting evidence candidate)",
      "",
    ],
  )
  for paper in data.get("selected_evidence_papers") or []:
    doi = paper.get("doi") or ""
    source = paper.get("source") or paper.get("source_name") or ""
    cited = paper.get("cited_by_count", "")
    lines.append(
      f"- {paper.get('title')} "
      f"(bucket={paper.get('relevance_bucket')}, score={paper.get('relevance_score', '')}, "
      f"doi={doi or 'n/a'}, source={source or 'n/a'}, cited_by={cited})",
    )
  if not data.get("selected_evidence_papers"):
    lines.append("- (none selected)")

  broad = data.get("broad_background_papers") or []
  if broad:
    lines.extend(["", "### broad background (Evidence Map外)", ""])
    for paper in broad[:5]:
      lines.append(f"- {paper.get('title')} ({paper.get('relevance_bucket')})")

  lines.extend(["", "## 3. Claim × Paper Candidate Map", ""])
  for item in data.get("evidence_map_items") or []:
    fallback_note = " [弱い対応]" if item.get("is_fallback_link") else ""
    doi = item.get("best_paper_doi") or ""
    source = item.get("best_paper_source") or ""
    cited = item.get("best_paper_cited_by_count", "")
    lines.append(
      f"- [{item.get('element_type')}] {item.get('element_text', '')[:80]} "
      f"→ {item.get('best_paper_title') or '(no paper)'} "
      f"({item.get('link_type')}, {item.get('confidence')}, bucket={item.get('relevance_bucket')})"
      f"{fallback_note}",
    )
    if item.get("best_paper_title"):
      lines.append(
        f"  - doi={doi or 'n/a'}, source={source or 'n/a'}, cited_by={cited if cited not in (None, '') else 'n/a'}",
      )
    lines.append(f"  - caveat: {item.get('caveat_japanese', '')[:120]}")
  if not data.get("evidence_map_items"):
    lines.append("- (no claim × paper items)")

  lines.extend(["", "## 4. Evidence Gaps", ""])
  for gap in data.get("evidence_gaps_japanese") or []:
    lines.append(f"- {gap}")
  if not data.get("evidence_gaps_japanese"):
    lines.append("- (none)")

  lines.extend(["", "## 5. 次アクション", ""])
  for action in data.get("next_actions_japanese") or []:
    lines.append(f"- {action}")

  lines.extend(["", "## 6. 注意", ""])
  for caveat in data.get("caveats_japanese") or [SYNTHESIS_CAVEAT]:
    lines.append(f"- {caveat}")
  lines.extend(
    [
      "- 論文は証明ではない",
      "- FTO/侵害/有効性判断ではない",
      "- 専門家レビューが必要",
      "",
      "※ 金額情報は含みません。",
    ],
  )
  return "\n".join(lines)


def save_evidence_map_synthesis_artifacts(
  synthesis: EvidenceMapSynthesis,
  output_dir: str | Path,
) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  payload = synthesis.to_dict()
  json_path = out / "evidence_map_synthesis.json"
  md_path = out / "evidence_map_synthesis.md"
  json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
  md_path.write_text(render_evidence_map_synthesis_markdown(synthesis), encoding="utf-8")
  items = [item.to_dict() for item in synthesis.evidence_map_items]
  return {
    "evidence_map_synthesis_json": str(json_path),
    "evidence_map_synthesis_md": str(md_path),
    "evidence_map_items_csv": save_records_csv(items, out / "evidence_map_items.csv"),
  }
