"""Web / company signal mapping report."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_web_signal_summary(result: dict[str, Any]) -> dict[str, Any]:
  quality_results = list(result.get("quality_results", []))
  do_not_cite = [item for item in quality_results if item.get("recommended_use") == "do_not_cite"]
  return {
    "signals_loaded": result.get("signals_loaded", 0),
    "high_quality_sources": result.get("high_quality_sources", 0),
    "medium_quality_sources": result.get("medium_quality_sources", 0),
    "low_quality_sources": result.get("low_quality_sources", 0),
    "unknown_quality_sources": result.get("unknown_quality_sources", 0),
    "patent_links": len(result.get("links", [])),
    "business_signal_candidates": result.get("business_signal_candidates", 0),
    "background_signals": result.get("background_signals", 0),
    "weak_signals": result.get("weak_signals", 0),
    "by_company": result.get("by_company", []),
    "by_cluster": result.get("by_cluster", []),
    "by_patent": result.get("by_patent", []),
    "links": result.get("links", []),
    "quality_results": quality_results,
    "do_not_cite_candidates": do_not_cite,
    "next_phases": ["Business View Agent", "Synthesis Report"],
  }


def render_web_signal_markdown(summary: dict[str, Any]) -> str:
  lines = [
    "# Web / Company Signal Mapping Report",
    "",
    "## 1. Summary",
    "",
    f"- signals loaded: {summary.get('signals_loaded', 0)}",
    f"- high quality sources: {summary.get('high_quality_sources', 0)}",
    f"- medium quality sources: {summary.get('medium_quality_sources', 0)}",
    f"- low quality sources: {summary.get('low_quality_sources', 0)}",
    f"- patent links: {summary.get('patent_links', 0)}",
    f"- business signal candidates: {summary.get('business_signal_candidates', 0)}",
    f"- background signals: {summary.get('background_signals', 0)}",
    f"- weak signals: {summary.get('weak_signals', 0)}",
    "",
    "## 2. Signals by Company",
    "",
  ]
  for row in summary.get("by_company", []):
    lines.append(
      f"- {row.get('normalized_company')}: signals={row.get('signal_count')}, "
      f"types={row.get('signal_types')}, linked_patents={row.get('linked_patents')}, "
      f"terms={row.get('major_technology_terms')}",
    )

  lines.extend(["", "## 3. Signals by Technology Cluster", ""])
  for row in summary.get("by_cluster", []):
    lines.append(
      f"- {row.get('primary_cluster_id')}: signals={row.get('signal_count')}, "
      f"companies={row.get('companies')}",
    )

  lines.extend(["", "## 4. Patent × Web Signal Links", ""])
  for link in summary.get("links", [])[:25]:
    lines.append(
      f"- {link.get('publication_number')} / {link.get('assignee')} ← "
      f"{link.get('source_title')} [{link.get('relation')}, score={link.get('relevance_score')}, "
      f"quality={link.get('source_quality_level')}] {link.get('caveat')}",
    )

  lines.extend(["", "## 5. Source Quality", ""])
  lines.append(f"- high: {summary.get('high_quality_sources', 0)}")
  lines.append(f"- medium: {summary.get('medium_quality_sources', 0)}")
  lines.append(f"- low: {summary.get('low_quality_sources', 0)}")
  lines.append(f"- unknown: {summary.get('unknown_quality_sources', 0)}")
  if summary.get("do_not_cite_candidates"):
    lines.append("")
    lines.append("do_not_cite candidates:")
    for item in summary["do_not_cite_candidates"][:10]:
      lines.append(f"- {item.get('signal_id')} ({item.get('quality_level')})")

  lines.extend(
    [
      "",
      "## 6. Caveats",
      "",
      "- Web signalは事業化の兆候候補であり、特定特許の実施や商用化を証明するものではない",
      "- 企業単位のニュースは、個別特許と直接対応しない場合がある",
      "- source qualityは情報源としての扱いやすさであり、内容の正しさや事業成功を保証しない",
      "- 人間によるURL確認が必要",
      "",
      "## 7. Next Phase",
      "",
    ],
  )
  for step in summary.get("next_phases", []):
    lines.append(f"- {step}")
  return "\n".join(lines)


def save_web_signal_report(markdown: str, output_dir: str | Path) -> str:
  path = Path(output_dir) / "web_signal_report.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(markdown, encoding="utf-8")
  return str(path)
