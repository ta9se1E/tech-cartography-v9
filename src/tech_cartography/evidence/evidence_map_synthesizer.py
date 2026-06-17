"""Evidence Map synthesis for a single patent deep-dive (Phase 20)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tech_cartography.evidence.claims_paper_candidate_mapper import map_claim_elements_to_paper_candidates
from tech_cartography.reports.project_export import load_records_csv

SYNTHESIS_CAVEAT = (
  "このEvidence Mapは、請求項と論文候補の対応を整理したものです。"
  "論文候補は技術背景の裏取り候補であり、特許主張を証明するものではありません。"
  "FTO・侵害・有効性の判断は行いません。専門家レビューが必要です。"
)

ITEM_CAVEAT = (
  "論文は supporting evidence candidate です。特許主張の証明ではありません。"
  "明細書・実施例が未入力の場合、技術妥当性の確認には限界があります。"
)


@dataclass
class EvidenceMapItem:
  publication_number: str = ""
  claim_element_id: str = ""
  element_type: str = ""
  element_text: str = ""
  selected_paper_count: int = 0
  best_paper_title: str | None = None
  best_paper_source: str | None = None
  best_paper_year: int | None = None
  best_paper_cited_by_count: int | None = None
  relevance_bucket: str | None = None
  link_type: str | None = None
  confidence: str = "weak"
  evidence_role: str = "supporting_evidence_candidate"
  caveat_japanese: str = ITEM_CAVEAT
  next_action_japanese: str = "技術者が論文候補を確認してください"

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class EvidenceMapSynthesis:
  publication_number: str = ""
  title: str | None = None
  assignee: str | None = None
  retrieval_route: str = "unknown"
  evidence_level: str = "unknown"
  claim_element_count: int = 0
  paper_query_count: int = 0
  paper_candidate_count: int = 0
  selected_evidence_paper_count: int = 0
  claim_paper_link_count: int = 0
  synthesis_status: str = "weak_no_selected_papers"
  key_findings_japanese: list[str] = field(default_factory=list)
  evidence_gaps_japanese: list[str] = field(default_factory=list)
  next_actions_japanese: list[str] = field(default_factory=list)
  caveats_japanese: list[str] = field(default_factory=list)
  evidence_map_items: list[EvidenceMapItem] = field(default_factory=list)
  selected_evidence_papers: list[dict[str, Any]] = field(default_factory=list)
  broad_background_papers: list[dict[str, Any]] = field(default_factory=list)
  element_type_counts: dict[str, int] = field(default_factory=dict)
  has_description: bool = False
  has_examples: bool = False

  def to_dict(self) -> dict[str, Any]:
    return {
      **asdict(self),
      "evidence_map_items": [item.to_dict() for item in self.evidence_map_items],
    }


def _find_first_existing(paths: list[Path]) -> Path | None:
  for path in paths:
    if path.exists():
      return path
  return None


def _latest_stage_dir(run_dir: Path, stage_name: str) -> Path | None:
  stage_root = run_dir / "stages" / stage_name
  if not stage_root.exists():
    return None
  candidates = sorted(stage_root.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
  return candidates[0] if candidates else stage_root


def _resolve_paths(
  run_dir: str | Path | None,
  publication_number: str,
  openalex_dir: str | Path | None,
) -> dict[str, Path | None]:
  pub = publication_number.strip()
  run_path = Path(run_dir) if run_dir else None
  oa_path = Path(openalex_dir) if openalex_dir else None

  ev_stage = _latest_stage_dir(run_path, "evidence_validation") if run_path else None
  oa_stage = _latest_stage_dir(run_path, "openalex_paper_evidence") if run_path else None

  return {
    "claim_elements": _find_first_existing(
      [
        *( [ev_stage / "claim_elements_from_manual_fulltext.csv"] if ev_stage else [] ),
        *( [ev_stage / "claim_elements.csv"] if ev_stage else [] ),
        Path(f"outputs/claims_paper_query_plans/{pub}/claim_elements.csv"),
      ],
    ),
    "paper_queries": _find_first_existing(
      [
        *( [ev_stage / "paper_query_candidates_from_claims.csv"] if ev_stage else [] ),
        Path(f"outputs/claims_paper_query_plans/{pub}/paper_query_candidates_from_claims.csv"),
      ],
    ),
    "selected_papers": _find_first_existing(
      [
        *( [Path(oa_path) / "selected_evidence_papers.csv"] if oa_path else [] ),
        *( [oa_stage / "selected_evidence_papers.csv"] if oa_stage else [] ),
        Path("outputs/openalex_limited_execution/selected_evidence_papers.csv"),
      ],
    ),
    "paper_records": _find_first_existing(
      [
        *( [Path(oa_path) / "openalex_paper_records.csv"] if oa_path else [] ),
        *( [oa_stage / "openalex_paper_records.csv"] if oa_stage else [] ),
        Path("outputs/openalex_limited_execution/openalex_paper_records.csv"),
      ],
    ),
    "paper_relevance": _find_first_existing(
      [
        *( [Path(oa_path) / "paper_candidate_relevance.csv"] if oa_path else [] ),
        *( [oa_stage / "paper_candidate_relevance.csv"] if oa_stage else [] ),
        Path("outputs/openalex_limited_execution/paper_candidate_relevance.csv"),
      ],
    ),
    "claim_paper_links": _find_first_existing(
      [
        *( [Path(oa_path) / "claim_paper_candidate_links.csv"] if oa_path else [] ),
        *( [oa_stage / "claim_paper_candidate_links.csv"] if oa_stage else [] ),
        Path("outputs/openalex_limited_execution/claim_paper_candidate_links.csv"),
      ],
    ),
    "source_quality": _find_first_existing(
      [
        *( [Path(oa_path) / "openalex_source_quality.csv"] if oa_path else [] ),
        *( [oa_stage / "openalex_source_quality.csv"] if oa_stage else [] ),
        Path("outputs/openalex_limited_execution/openalex_source_quality.csv"),
      ],
    ),
    "manual_input": _find_first_existing(
      [
        Path(f"outputs/manual_fulltext_inputs/{pub}.json"),
        Path(f"outputs/manual_fulltext_inputs/{pub.replace('-', '')}.json"),
      ],
    ),
    "fulltext_records": _find_first_existing(
      [
        *( [_latest_stage_dir(run_path, "top5_fulltext_collection") / "top5_fulltext_records.json"] if run_path and _latest_stage_dir(run_path, "top5_fulltext_collection") else [] ),
      ],
    ),
  }


def load_claim_elements_for_synthesis(path: str | Path | None) -> list[dict[str, Any]]:
  if not path or not Path(path).exists():
    return []
  rows = load_records_csv(str(path))
  return [row for row in rows if str(row.get("element_id") or row.get("element_type") or "")]


def load_selected_evidence_papers_for_synthesis(path: str | Path | None) -> list[dict[str, Any]]:
  if not path or not Path(path).exists():
    return []
  return load_records_csv(str(path))


def load_paper_relevance_for_synthesis(path: str | Path | None) -> list[dict[str, Any]]:
  if not path or not Path(path).exists():
    return []
  return load_records_csv(str(path))


def load_claim_paper_links_for_synthesis(path: str | Path | None) -> list[dict[str, Any]]:
  if not path or not Path(path).exists():
    return []
  return load_records_csv(str(path))


def _load_manual_input(path: Path | None) -> dict[str, Any]:
  if not path or not path.exists():
    return {}
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except json.JSONDecodeError:
    return {}


def _load_patent_metadata(
  publication_number: str,
  claim_elements: list[dict[str, Any]],
  manual_input: dict[str, Any],
  fulltext_path: Path | None,
) -> dict[str, Any]:
  title = manual_input.get("title")
  assignee = manual_input.get("assignee")
  retrieval_route = str(manual_input.get("input_route") or "manual_claims_only")
  evidence_level = "low_fulltext_evidence"
  has_description = bool(str(manual_input.get("description_text") or "").strip())
  has_examples = bool(str(manual_input.get("examples_text") or "").strip())

  if fulltext_path and fulltext_path.exists():
    data = json.loads(fulltext_path.read_text(encoding="utf-8"))
    records = data if isinstance(data, list) else data.get("retrieved_records", [])
    for row in records:
      if str(row.get("publication_number") or "") == publication_number:
        title = title or row.get("title")
        assignee = assignee or row.get("assignee")
        retrieval_route = str(row.get("retrieval_status") or retrieval_route)
        evidence_level = str(row.get("evidence_level") or evidence_level)
        break

  if claim_elements:
    first = claim_elements[0]
    title = title or first.get("title")

  return {
    "title": title or publication_number,
    "assignee": assignee or "",
    "retrieval_route": retrieval_route,
    "evidence_level": evidence_level,
    "has_description": has_description,
    "has_examples": has_examples,
  }


def classify_synthesis_status(
  *,
  claim_element_count: int,
  paper_candidate_count: int,
  selected_evidence_paper_count: int,
  has_claims: bool,
  has_description: bool,
) -> str:
  if claim_element_count == 0 and not has_claims:
    return "blocked_no_claims"
  if selected_evidence_paper_count > 0:
    return "ready_with_selected_papers"
  if paper_candidate_count > 0:
    return "weak_no_selected_papers"
  if claim_element_count > 0 and not has_description:
    return "manual_description_recommended"
  if claim_element_count > 0:
    return "ready_limited_claims_only"
  return "weak_no_selected_papers"


def build_key_findings_japanese(
  synthesis: EvidenceMapSynthesis,
  relevance_rows: list[dict[str, Any]],
) -> list[str]:
  findings: list[str] = []
  if synthesis.claim_element_count > 0:
    type_summary = ", ".join(f"{k}={v}" for k, v in sorted(synthesis.element_type_counts.items()))
    findings.append(f"manual claimsから {synthesis.claim_element_count} 件のClaim Elementを抽出しました（{type_summary}）。")
  if synthesis.paper_query_count > 0:
    findings.append(f"claims-based paper query候補を {synthesis.paper_query_count} 件生成しました。")
  if synthesis.selected_evidence_paper_count > 0:
    findings.append(
      f"OpenAlex候補 {synthesis.paper_candidate_count} 件のうち、"
      f"Evidence Map向けに {synthesis.selected_evidence_paper_count} 件を選定しました。",
    )
    for paper in synthesis.selected_evidence_papers[:3]:
      bucket = paper.get("relevance_bucket", "")
      findings.append(f"代表論文候補: {paper.get('title')} ({bucket}) — supporting evidence candidate")
  elif synthesis.paper_candidate_count > 0:
    findings.append("論文候補はあるが、Evidence Map向けのselected evidence papersは未選定または0件です。")
  else:
    findings.append("OpenAlex paper candidatesはまだありません。plan_onlyまたは未実行の可能性があります。")
  if synthesis.claim_paper_link_count > 0:
    findings.append(f"Claim × Paper candidate linkを {synthesis.claim_paper_link_count} 件作成しました。")
  broad = [r for r in relevance_rows if r.get("relevance_bucket") == "broad_composite_background"]
  if broad:
    findings.append(f"広い複合材料レビュー {len(broad)} 件は背景候補として扱い、Evidence Mapからは除外しました。")
  return findings


def build_evidence_gaps_japanese(
  *,
  has_description: bool,
  has_examples: bool,
  retrieval_route: str,
  selected_count: int,
  link_count: int,
  claim_element_count: int,
) -> list[str]:
  gaps: list[str] = []
  if "manual" in retrieval_route.lower() or "dry_run" in retrieval_route.lower():
    gaps.append("BigQuery fulltextは未取得または限定的です。Manual Routeでclaimsを利用しています。")
  if not has_description:
    gaps.append("明細書（description）が未入力です。材料・プロセス・数値条件の裏取り精度が限定的です。")
  if not has_examples:
    gaps.append("実施例・測定条件が未確認です。物性数値の裏取りは不足しています。")
  if claim_element_count > 0 and selected_count == 0:
    gaps.append("selected evidence papersが0件です。OpenAlex実行またはrelevance filterの見直しが必要です。")
  if claim_element_count > 0 and link_count == 0:
    gaps.append("Claim × Paper linkが未作成です。claim elementsと論文候補の対応確認が必要です。")
  gaps.append("claims_only由来のため、論文は証明ではなく supporting evidence candidate としてのみ扱えます。")
  return gaps


def build_next_actions_japanese(
  *,
  synthesis_status: str,
  has_description: bool,
  selected_count: int,
) -> list[str]:
  actions: list[str] = []
  if not has_description or synthesis_status == "manual_description_recommended":
    actions.append("descriptionをmanualで追加する（Google Patentsから明細書を貼り付け）")
  actions.append("実施例・測定条件を追加する")
  if selected_count == 0:
    actions.append("OpenAlex queryを技術者が確認し、必要なら限定実行する")
  else:
    actions.append("selected evidence papersを技術者が確認する")
  actions.append("OpenAlex queryの妥当性を技術者が確認する")
  actions.append("CN Strategic Watch候補をPDF/manualで確認する")
  return actions


def build_evidence_map_items(
  claim_elements: list[dict[str, Any]],
  links: list[dict[str, Any]],
  selected_papers: list[dict[str, Any]],
  *,
  publication_number: str,
  has_description: bool = False,
) -> list[EvidenceMapItem]:
  if not links and claim_elements and selected_papers:
    enriched_papers = list(selected_papers)
    links = map_claim_elements_to_paper_candidates(
      claim_elements,
      enriched_papers,
      has_description=has_description,
    )

  paper_by_id = {
    str(p.get("paper_id") or p.get("openalex_id") or ""): p
    for p in selected_papers
    if str(p.get("paper_id") or p.get("openalex_id") or "")
  }

  items: list[EvidenceMapItem] = []
  for element in claim_elements:
    element_id = str(element.get("element_id") or "")
    element_links = [link for link in links if str(link.get("element_id") or "") == element_id]
    if not element_links and links:
      element_links = [
        link for link in links
        if str(link.get("element_type") or "") == str(element.get("element_type") or "")
      ]
    element_links.sort(key=lambda row: float(row.get("link_score", 0)), reverse=True)
    best = element_links[0] if element_links else {}
    paper_id = str(best.get("paper_id") or "")
    paper = paper_by_id.get(paper_id, {})

    confidence = str(best.get("confidence") or "weak")
    if confidence == "high":
      confidence = "medium"

    items.append(
      EvidenceMapItem(
        publication_number=publication_number,
        claim_element_id=element_id,
        element_type=str(element.get("element_type") or "unknown"),
        element_text=str(element.get("element_text") or ""),
        selected_paper_count=len({str(l.get("paper_id")) for l in element_links if l.get("paper_id")}),
        best_paper_title=best.get("paper_title") or paper.get("title"),
        best_paper_source=paper.get("source_name") or paper.get("journal"),
        best_paper_year=int(paper["publication_year"]) if paper.get("publication_year") not in (None, "") else None,
        best_paper_cited_by_count=int(paper["cited_by_count"]) if paper.get("cited_by_count") not in (None, "") else None,
        relevance_bucket=best.get("relevance_bucket") or paper.get("relevance_bucket"),
        link_type=best.get("link_type"),
        confidence=confidence,
        evidence_role=str(best.get("evidence_role") or "supporting_evidence_candidate"),
        caveat_japanese=str(best.get("caveat_japanese") or ITEM_CAVEAT),
        next_action_japanese=(
          "論文候補を確認（supporting evidence candidate）"
          if best
          else "OpenAlex queryを実行するか、論文候補を追加する"
        ),
      ),
    )
  return items


def build_evidence_map_synthesis(
  run_dir: str | Path | None,
  publication_number: str,
  openalex_dir: str | Path | None = None,
  *,
  allow_weak_no_papers: bool = True,
) -> EvidenceMapSynthesis:
  paths = _resolve_paths(run_dir, publication_number, openalex_dir)
  manual = _load_manual_input(paths.get("manual_input"))
  has_claims = bool(str(manual.get("claims_text") or "").strip())

  claim_elements = load_claim_elements_for_synthesis(paths.get("claim_elements"))
  if not claim_elements and has_claims:
    claim_elements = [{"element_id": f"{publication_number}-manual", "element_type": "material", "element_text": "manual claims loaded"}]

  paper_queries = load_records_csv(str(paths["paper_queries"])) if paths.get("paper_queries") else []
  selected_papers = load_selected_evidence_papers_for_synthesis(paths.get("selected_papers"))
  paper_records = load_records_csv(str(paths["paper_records"])) if paths.get("paper_records") else []
  relevance_rows = load_paper_relevance_for_synthesis(paths.get("paper_relevance"))
  links = load_claim_paper_links_for_synthesis(paths.get("claim_paper_links"))

  meta = _load_patent_metadata(publication_number, claim_elements, manual, paths.get("fulltext_records"))
  broad_papers = [
    row for row in relevance_rows
    if row.get("relevance_bucket") in {"broad_composite_background", "likely_off_topic"}
  ]

  element_type_counts: dict[str, int] = {}
  for element in claim_elements:
    etype = str(element.get("element_type") or "unknown")
    element_type_counts[etype] = element_type_counts.get(etype, 0) + 1

  selected_count = len(selected_papers)
  paper_candidate_count = len(paper_records) or len(relevance_rows)
  link_count = len(links)

  status = classify_synthesis_status(
    claim_element_count=len(claim_elements),
    paper_candidate_count=paper_candidate_count,
    selected_evidence_paper_count=selected_count,
    has_claims=has_claims or len(claim_elements) > 0,
    has_description=bool(meta["has_description"]),
  )
  if not allow_weak_no_papers and status == "weak_no_selected_papers":
    status = "ready_limited_claims_only"

  items = build_evidence_map_items(
    claim_elements,
    links,
    selected_papers,
    publication_number=publication_number,
    has_description=bool(meta["has_description"]),
  )

  synthesis = EvidenceMapSynthesis(
    publication_number=publication_number,
    title=str(meta["title"]),
    assignee=str(meta["assignee"]) or None,
    retrieval_route=str(meta["retrieval_route"]),
    evidence_level=str(meta["evidence_level"]),
    claim_element_count=len(claim_elements),
    paper_query_count=len(paper_queries),
    paper_candidate_count=paper_candidate_count,
    selected_evidence_paper_count=selected_count,
    claim_paper_link_count=max(link_count, len(links)),
    synthesis_status=status,
    evidence_map_items=items,
    selected_evidence_papers=selected_papers,
    broad_background_papers=broad_papers,
    element_type_counts=element_type_counts,
    has_description=bool(meta["has_description"]),
    has_examples=bool(meta["has_examples"]),
    caveats_japanese=[SYNTHESIS_CAVEAT],
  )
  synthesis.key_findings_japanese = build_key_findings_japanese(synthesis, relevance_rows)
  synthesis.evidence_gaps_japanese = build_evidence_gaps_japanese(
    has_description=bool(meta["has_description"]),
    has_examples=bool(meta["has_examples"]),
    retrieval_route=str(meta["retrieval_route"]),
    selected_count=selected_count,
    link_count=max(link_count, len(links)),
    claim_element_count=len(claim_elements),
  )
  synthesis.next_actions_japanese = build_next_actions_japanese(
    synthesis_status=status,
    has_description=bool(meta["has_description"]),
    selected_count=selected_count,
  )
  return synthesis
