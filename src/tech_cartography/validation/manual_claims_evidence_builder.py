"""Rule-based Claim Element extraction and Evidence Map skeleton builder (Phase 24.4A.3)."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.validation.theme_validation import (
  _read_manual_claims_text,
  manual_claims_json_path,
)

SKELETON_CAUTION_EN = (
  "This is an Evidence Map skeleton generated from user-provided manual claims. "
  "It is not a final evidence map. Paper/Web evidence has not been verified yet."
)
SKELETON_CAUTION_JA = (
  "これはユーザー提供のManual Claimsから作成したEvidence Map skeletonです。"
  "最終的なEvidence Mapではありません。論文・Web evidenceは未検証です。"
)
ELEMENT_EXTRACTION_CAVEAT = "rule-based extraction candidate; not AI-generated; low confidence"

MATERIAL_TERMS = (
  "PAN",
  "ポリアクリロニトリル",
  "炭素繊維前駆体",
  "カルボキシル基",
  "イタコン酸",
  "メタクリル酸",
)
PROCESS_TERMS = (
  "紡糸原液",
  "凝固浴",
  "乾燥",
  "乾燥熱履歴",
)
PROPERTY_TERMS = (
  "カルボン酸反応指数",
  "ボイド",
  "緻密化",
  "毛羽",
  "65℃",
  "700以下",
)
ALL_RULE_TERMS = MATERIAL_TERMS + PROCESS_TERMS + PROPERTY_TERMS

CLAIM_HEADER_PATTERN = re.compile(
  r"(?:【請求項\s*([０-９0-9]+)】|Claim\s+(\d+)|^請求項\s*([０-９0-9]+)\s*[:：.]?)",
  re.IGNORECASE | re.MULTILINE,
)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_claim_number(raw: str) -> str:
  table = str.maketrans("０１２３４５６７８９", "0123456789")
  return str(raw).translate(table).strip()


def evidence_map_output_dir(project_root: Path | str, publication_number: str) -> Path:
  pub = str(publication_number).strip()
  return Path(project_root) / "outputs" / "evidence_map_synthesis" / pub


@dataclass
class ManualClaimElement:
  element_id: str
  publication_number: str
  claim_number: str
  element_text: str
  keywords: list[str] = field(default_factory=list)
  process_terms: list[str] = field(default_factory=list)
  material_terms: list[str] = field(default_factory=list)
  property_terms: list[str] = field(default_factory=list)
  caveat: str = ELEMENT_EXTRACTION_CAVEAT

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class EvidenceMapSkeleton:
  publication_number: str
  created_at: str
  source_manual_claims_path: str
  claim_elements: list[ManualClaimElement] = field(default_factory=list)
  query_plan: list[dict[str, Any]] = field(default_factory=list)
  evidence_gaps: list[str] = field(default_factory=list)
  next_actions: list[str] = field(default_factory=list)
  caveats: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      "publication_number": self.publication_number,
      "created_at": self.created_at,
      "source_manual_claims_path": self.source_manual_claims_path,
      "claim_elements": [element.to_dict() for element in self.claim_elements],
      "query_plan": self.query_plan,
      "evidence_gaps": self.evidence_gaps,
      "next_actions": self.next_actions,
      "caveats": self.caveats,
      "caution_en": SKELETON_CAUTION_EN,
      "caution_ja": SKELETON_CAUTION_JA,
    }


def load_manual_claims(publication_number: str, output_dir: Path | str) -> dict[str, Any]:
  path = manual_claims_json_path(output_dir, publication_number)
  if not path.exists():
    raise FileNotFoundError(f"Manual claims not found: {path}")
  data = json.loads(path.read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError(f"Invalid manual claims JSON: {path}")
  claims_text = str(data.get("claims_text", "")).strip()
  if not claims_text:
    raise ValueError(f"claims_text is empty in {path}")
  data["claims_text"] = claims_text
  data["_path"] = str(path)
  return data


def split_claims_text(claims_text: str) -> list[dict[str, str]]:
  text = str(claims_text or "").strip()
  if not text:
    return []

  matches = list(CLAIM_HEADER_PATTERN.finditer(text))
  if not matches:
    return [{"claim_number": "1", "claim_text": text}]

  claims: list[dict[str, str]] = []
  for index, match in enumerate(matches):
    claim_number = next(
      (group for group in match.groups() if group),
      str(index + 1),
    )
    start = match.end()
    end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
    claim_text = text[start:end].strip()
    if claim_text:
      claims.append(
        {
          "claim_number": _normalize_claim_number(claim_number),
          "claim_text": claim_text,
        },
      )
  return claims


def _match_terms(text: str, terms: tuple[str, ...]) -> list[str]:
  found: list[str] = []
  for term in terms:
    if term and term in text and term not in found:
      found.append(term)
  return found


def extract_claim_elements_from_text(
  publication_number: str,
  claims_text: str,
) -> list[ManualClaimElement]:
  pub = str(publication_number).strip()
  elements: list[ManualClaimElement] = []
  for claim in split_claims_text(claims_text):
    claim_number = claim["claim_number"]
    claim_text = claim["claim_text"]
    material_terms = _match_terms(claim_text, MATERIAL_TERMS)
    process_terms = _match_terms(claim_text, PROCESS_TERMS)
    property_terms = _match_terms(claim_text, PROPERTY_TERMS)
    keywords = list(dict.fromkeys(material_terms + process_terms + property_terms))
    elements.append(
      ManualClaimElement(
        element_id=f"{pub}-claim-{claim_number}",
        publication_number=pub,
        claim_number=claim_number,
        element_text=claim_text,
        keywords=keywords,
        process_terms=process_terms,
        material_terms=material_terms,
        property_terms=property_terms,
      ),
    )
  return elements


def build_query_plan_from_claim_elements(
  elements: list[ManualClaimElement],
) -> list[dict[str, Any]]:
  plans: list[dict[str, Any]] = []
  for element in elements:
    must_have = list(element.material_terms[:2])
    should_have = list(element.process_terms[:2] + element.property_terms[:2])
    if not must_have and element.keywords:
      must_have = [element.keywords[0]]
    if not must_have and not should_have:
      continue
    plans.append(
      {
        "element_id": element.element_id,
        "claim_number": element.claim_number,
        "intent_id": f"evidence_skeleton_{element.element_id}",
        "purpose": "Paper candidate query plan (not executed)",
        "must_have_terms": must_have,
        "should_have_terms": should_have,
        "exclude_terms": [],
        "notes": [
          "Generated from rule-based claim element extraction.",
          "OpenAlex execution required; not run in this phase.",
        ],
      },
    )
  return plans


def build_evidence_map_skeleton(
  publication_number: str,
  manual_claims_path: Path | str,
) -> EvidenceMapSkeleton:
  path = Path(manual_claims_path)
  pub = str(publication_number).strip()
  claims_text = _read_manual_claims_text(path)
  if not claims_text:
    raise ValueError(f"No claims_text in {path}")

  elements = extract_claim_elements_from_text(pub, claims_text)
  query_plan = build_query_plan_from_claim_elements(elements)
  evidence_gaps = [
    "Paper candidates have not been retrieved (OpenAlex not executed).",
    "Web signal candidates have not been retrieved (Tavily not executed).",
    "Claim-to-paper links are not built.",
    "Strategic watch brief is not generated.",
  ]
  next_actions = [
    "Review claim_elements.csv and query_plan.json.",
    "Run OpenAlex with explicit consent to retrieve paper candidates.",
    "Run Tavily with explicit consent to retrieve web signal candidates.",
    "Do not treat rule-based keywords as legal or FTO conclusions.",
  ]
  caveats = [
    ELEMENT_EXTRACTION_CAVEAT,
    SKELETON_CAUTION_EN,
    SKELETON_CAUTION_JA,
  ]
  return EvidenceMapSkeleton(
    publication_number=pub,
    created_at=_utc_now_iso(),
    source_manual_claims_path=str(path),
    claim_elements=elements,
    query_plan=query_plan,
    evidence_gaps=evidence_gaps,
    next_actions=next_actions,
    caveats=caveats,
  )


def render_evidence_map_skeleton_markdown(skeleton: EvidenceMapSkeleton) -> str:
  lines = [
    f"# Evidence Map Skeleton: {skeleton.publication_number}",
    "",
    f"- created_at: {skeleton.created_at}",
    f"- source_manual_claims_path: {skeleton.source_manual_claims_path}",
    "",
    "## Caution",
    "",
    f"- {SKELETON_CAUTION_EN}",
    f"- {SKELETON_CAUTION_JA}",
    "",
    "## Claim elements (rule-based candidates)",
    "",
  ]
  for element in skeleton.claim_elements:
    lines.append(f"### Claim {element.claim_number} ({element.element_id})")
    lines.append(f"- keywords: {', '.join(element.keywords) or '（なし）'}")
    lines.append(f"- material_terms: {', '.join(element.material_terms) or '（なし）'}")
    lines.append(f"- process_terms: {', '.join(element.process_terms) or '（なし）'}")
    lines.append(f"- property_terms: {', '.join(element.property_terms) or '（なし）'}")
    lines.append(f"- caveat: {element.caveat}")
    preview = element.element_text[:240].replace("\n", " ")
    lines.append(f"- text_preview: {preview}…")
    lines.append("")

  lines.extend(["## Evidence gaps", ""])
  for gap in skeleton.evidence_gaps:
    lines.append(f"- {gap}")

  lines.extend(["", "## Next actions", ""])
  for action in skeleton.next_actions:
    lines.append(f"- {action}")

  lines.extend(
    [
      "",
      "## Note",
      "",
      "- This skeleton is separate from US-12565719-B2 demo full evidence map.",
      "- FTO, infringement, and validity conclusions are not provided.",
      "",
    ],
  )
  return "\n".join(lines)


def render_evidence_gaps_md(skeleton: EvidenceMapSkeleton) -> str:
  lines = ["# Evidence Gaps", "", f"publication_number: {skeleton.publication_number}", ""]
  for gap in skeleton.evidence_gaps:
    lines.append(f"- {gap}")
  lines.extend(["", SKELETON_CAUTION_JA, ""])
  return "\n".join(lines)


def render_next_actions_md(skeleton: EvidenceMapSkeleton) -> str:
  lines = ["# Next Actions", "", f"publication_number: {skeleton.publication_number}", ""]
  for action in skeleton.next_actions:
    lines.append(f"- {action}")
  lines.extend(
    [
      "",
      "- 論文候補を取得するには OpenAlex 等の外部API実行が必要です。",
      "- Webシグナル候補を取得するには Tavily 等の外部API実行が必要です。",
      "- この段階では、論文・Webシグナルによる裏取りは未完了です。",
      "",
    ],
  )
  return "\n".join(lines)


def save_evidence_map_skeleton(
  skeleton: EvidenceMapSkeleton,
  output_dir: Path | str,
) -> dict[str, Path]:
  out = evidence_map_output_dir(output_dir, skeleton.publication_number)
  out.mkdir(parents=True, exist_ok=True)
  paths = {
    "evidence_map_skeleton_md": out / "evidence_map_skeleton.md",
    "evidence_map_skeleton_json": out / "evidence_map_skeleton.json",
    "claim_elements_csv": out / "claim_elements.csv",
    "query_plan_json": out / "query_plan.json",
    "evidence_gaps_md": out / "evidence_gaps.md",
    "next_actions_md": out / "next_actions.md",
  }

  paths["evidence_map_skeleton_md"].write_text(
    render_evidence_map_skeleton_markdown(skeleton),
    encoding="utf-8",
  )
  paths["evidence_map_skeleton_json"].write_text(
    json.dumps(skeleton.to_dict(), indent=2, ensure_ascii=False),
    encoding="utf-8",
  )
  paths["evidence_gaps_md"].write_text(render_evidence_gaps_md(skeleton), encoding="utf-8")
  paths["next_actions_md"].write_text(render_next_actions_md(skeleton), encoding="utf-8")

  fieldnames = [
    "element_id",
    "publication_number",
    "claim_number",
    "element_text",
    "keywords",
    "process_terms",
    "material_terms",
    "property_terms",
    "caveat",
  ]
  with paths["claim_elements_csv"].open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    for element in skeleton.claim_elements:
      row = element.to_dict()
      for key in ("keywords", "process_terms", "material_terms", "property_terms"):
        row[key] = "|".join(row[key])
      writer.writerow(row)

  paths["query_plan_json"].write_text(
    json.dumps(skeleton.query_plan, indent=2, ensure_ascii=False),
    encoding="utf-8",
  )
  return paths


def evidence_map_skeleton_exists(project_root: Path | str, publication_number: str) -> bool:
  out = evidence_map_output_dir(project_root, publication_number)
  return (out / "evidence_map_skeleton.json").exists()


def full_evidence_map_exists(project_root: Path | str, publication_number: str) -> bool:
  out = evidence_map_output_dir(project_root, publication_number)
  return (out / "evidence_map_synthesis.json").exists()
