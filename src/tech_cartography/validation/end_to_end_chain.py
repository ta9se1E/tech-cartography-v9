"""JP seed end-to-end validation chain (Phase 24.4C)."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from tech_cartography.delivery.digest_diff import build_digest_snapshot, compare_digest_snapshots
from tech_cartography.delivery.weekly_digest import WeeklyDigest, build_weekly_digest
from tech_cartography.evidence.openalex_limited_executor import (
  LIMITED_EXECUTION_CAVEAT,
  OpenAlexExecutionConfig,
  execute_openalex_limited,
  save_openalex_limited_artifacts,
)
from tech_cartography.evidence.paper_candidate_relevance_filter import (
  apply_relevance_to_paper_records,
  save_paper_candidate_relevance_artifacts,
)
from tech_cartography.reports.project_export import load_records_csv, save_records_csv
from tech_cartography.strategic_watch.brief_builder import build_strategic_watch_brief
from tech_cartography.strategic_watch.store import save_strategic_watch_brief
from tech_cartography.validation.manual_claims_evidence_builder import evidence_map_output_dir
from tech_cartography.validation.seed_progress import inspect_seed_progress
from tech_cartography.validation.theme_validation import has_manual_claims
from tech_cartography.web_signals.linker import (
  LinkScoringConfig,
  build_web_signal_link_pack,
  save_web_signal_link_pack,
)
from tech_cartography.web_signals.tavily_adapter import get_tavily_api_key
from tech_cartography.web_signals.tavily_runner import TavilyRunConfig, run_tavily_web_signal_pipeline

CHAIN_CAUTION = (
  "本チェーンは FTO、侵害、有効性の法的判断ではありません。"
  "Paper/Web/Link/Watch はすべて確認候補であり、最終結論ではありません。"
)
PAPER_CAUTION = (
  "論文候補は supporting evidence candidate であり、特許請求項の証明ではありません。"
)
WEB_SIGNAL_CAUTION = (
  "Webシグナルは signal candidate です。money/national_project/IR は原典確認が必要です。"
)
LINK_CAUTION = "Link Candidate は確認候補であり、直接関係の証明ではありません。"
WATCH_CAUTION = "Strategic Watch は重点監視候補であり、最終結論ではありません。"
DIGEST_CAUTION = "Digest は preview only です。送信は行いません。"

STAGE_LABELS = {
  "pass": "pass",
  "query_plan_ready": "query_plan_ready",
  "external_api_required": "external_api_required",
  "blocked_missing_tavily_config": "blocked_missing_tavily_config",
  "blocked_missing_paper_or_web_signal": "blocked_missing_paper_or_web_signal",
  "paper_link_missing": "paper_link_missing",
  "web_signal_missing": "web_signal_missing",
  "limited_watch_brief": "limited_watch_brief",
  "manual_input_required": "manual_input_required",
  "output_missing": "output_missing",
  "blocked": "blocked",
}


@dataclass
class EndToEndChainConfig:
  theme_id: str
  theme_name: str
  publication_numbers: list[str]
  output_root: str
  max_papers: int = 5
  max_web_signals: int = 10
  run_openalex: bool = False
  run_tavily: bool = False
  run_bigquery: bool = False
  cache_first: bool = True
  dry_run: bool = True
  allow_external_api: bool = False
  created_by: str = "ui"

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class SeedChainStatus:
  publication_number: str
  stage2_manual_claims: str
  stage3_evidence_skeleton: str
  stage4_paper_candidates: str
  stage5_web_signals: str
  stage6_link_candidates: str
  stage7_strategic_watch: str
  stage8_digest: str
  overall_status: str
  next_action: str
  output_paths: dict[str, str] = field(default_factory=dict)
  caveats: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class EndToEndChainResult:
  theme_id: str
  created_at: str
  seed_statuses: list[SeedChainStatus]
  completed_count: int
  blocked_count: int
  external_api_required_count: int
  output_paths: dict[str, str] = field(default_factory=dict)
  caveats: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      "theme_id": self.theme_id,
      "created_at": self.created_at,
      "seed_statuses": [s.to_dict() for s in self.seed_statuses],
      "completed_count": self.completed_count,
      "blocked_count": self.blocked_count,
      "external_api_required_count": self.external_api_required_count,
      "output_paths": self.output_paths,
      "caveats": self.caveats,
    }


def _utc_now() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _root(config: EndToEndChainConfig) -> Path:
  return Path(config.output_root)


def paper_candidates_dir(root: Path, publication_number: str) -> Path:
  return root / "outputs" / "paper_candidates" / publication_number


def web_signals_dir(root: Path, theme_id: str, publication_number: str) -> Path:
  return root / "outputs" / "web_signals" / f"{theme_id}_{publication_number}"


def link_candidates_dir(root: Path, publication_number: str) -> Path:
  return root / "outputs" / "web_signal_links" / publication_number


def strategic_watch_dir(root: Path, publication_number: str) -> Path:
  return root / "outputs" / "strategic_watch_briefs" / publication_number


def end_to_end_output_dir(root: Path, theme_id: str) -> Path:
  return root / "outputs" / "validation" / "end_to_end_chain" / theme_id


def _load_json(path: Path) -> Any:
  if not path.exists():
    return None
  return json.loads(path.read_text(encoding="utf-8"))


def _load_claim_elements(ev_dir: Path) -> list[dict[str, Any]]:
  path = ev_dir / "claim_elements.csv"
  if not path.exists():
    return []
  return load_records_csv(str(path))


def _openalex_candidates_from_plan(
  plan_items: list[dict[str, Any]],
  publication_number: str,
) -> list[dict[str, Any]]:
  candidates: list[dict[str, Any]] = []
  for item in plan_items:
    must = list(item.get("must_have_terms") or [])
    should = list(item.get("should_have_terms") or [])
    terms = [str(t).strip() for t in must + should if str(t).strip()]
    if not terms:
      continue
    query = " ".join(terms[:5])
    candidates.append(
      {
        "publication_number": publication_number,
        "element_id": item.get("element_id", ""),
        "query_id": item.get("element_id") or item.get("intent_id", ""),
        "query": query,
        "query_type": "material_process",
        "confidence": "medium",
        "purpose": item.get("purpose", "supporting evidence candidate"),
      },
    )
  return candidates


def build_paper_query_plan_from_skeleton(
  publication_number: str,
  output_root: Path | str,
) -> dict[str, Any]:
  root = Path(output_root)
  pub = str(publication_number).strip()
  ev_dir = evidence_map_output_dir(root, pub)
  skeleton_path = ev_dir / "evidence_map_skeleton.json"
  query_plan_path = ev_dir / "query_plan.json"
  claim_elements = _load_claim_elements(ev_dir)

  plan_items: list[dict[str, Any]] = []
  if query_plan_path.exists():
    raw = _load_json(query_plan_path)
    if isinstance(raw, list):
      plan_items = raw
  if not plan_items and skeleton_path.exists():
    skel = _load_json(skeleton_path) or {}
    plan_items = list(skel.get("query_plan") or [])

  openalex_candidates = _openalex_candidates_from_plan(plan_items, pub)
  payload = {
    "publication_number": pub,
    "created_at": _utc_now(),
    "source": {
      "query_plan_json": str(query_plan_path),
      "claim_elements_csv": str(ev_dir / "claim_elements.csv"),
      "evidence_map_skeleton_json": str(skeleton_path),
    },
    "query_plan_items": plan_items,
    "openalex_query_candidates": openalex_candidates,
    "caveats": [PAPER_CAUTION, LIMITED_EXECUTION_CAVEAT],
    "notes": "Paper query plan from Evidence Map skeleton. Not executed unless allow_external_api=true.",
  }
  return payload


def _save_paper_query_plan(payload: dict[str, Any], out_dir: Path) -> Path:
  out_dir.mkdir(parents=True, exist_ok=True)
  path = out_dir / "paper_query_plan.json"
  path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
  return path


def _stage2_status(root: Path, pub: str) -> str:
  ok, status = has_manual_claims(pub, root)
  return "pass" if ok and status == "saved" else "manual_input_required"


def _stage3_status(root: Path, pub: str) -> str:
  ev_dir = evidence_map_output_dir(root, pub)
  if (ev_dir / "evidence_map_synthesis.json").exists():
    return "pass"
  if (ev_dir / "evidence_map_skeleton.json").exists():
    return "pass"
  return "output_missing"


def _stage4_status(root: Path, pub: str) -> tuple[str, str]:
  pdir = paper_candidates_dir(root, pub)
  if (pdir / "selected_evidence_papers.csv").exists() or (pdir / "paper_candidates.csv").exists():
    return "pass", str(pdir)
  if (pdir / "paper_query_plan.json").exists():
    return "query_plan_ready", str(pdir)
  return "external_api_required", str(pdir)


def _stage5_status(root: Path, theme_id: str, pub: str) -> tuple[str, str]:
  wdir = web_signals_dir(root, theme_id, pub)
  review = wdir / "review_pack" / "high_priority_web_signals.csv"
  if (wdir / "web_signals.csv").exists() or review.exists():
    return "pass", str(wdir)
  if (wdir / "web_signal_query_plan.json").exists():
    return "query_plan_ready", str(wdir)
  return "external_api_required", str(wdir)


def _stage6_status(root: Path, pub: str) -> tuple[str, str]:
  ldir = link_candidates_dir(root, pub)
  if (ldir / "web_signal_link_candidates.csv").exists():
    return "pass", str(ldir)
  return "blocked_missing_paper_or_web_signal", str(ldir)


def _stage7_status(root: Path, pub: str) -> tuple[str, str]:
  sdir = strategic_watch_dir(root, pub)
  if (sdir / "strategic_watch_brief.json").exists():
    brief = _load_json(sdir / "strategic_watch_brief.json") or {}
    if brief.get("limited_watch_brief"):
      return "limited_watch_brief", str(sdir)
    return "pass", str(sdir)
  return "output_missing", str(sdir)


def _stage8_status(root: Path, pub: str) -> tuple[str, str]:
  md = root / "outputs" / "delivery" / f"jp_seed_digest_{pub}.md"
  if md.exists():
    return "pass", str(md)
  return "output_missing", str(md)


def _compute_overall(status: SeedChainStatus) -> str:
  stages = [
    status.stage2_manual_claims,
    status.stage3_evidence_skeleton,
    status.stage4_paper_candidates,
    status.stage5_web_signals,
    status.stage6_link_candidates,
    status.stage7_strategic_watch,
    status.stage8_digest,
  ]
  if all(s == "pass" for s in stages):
    return "complete"
  if status.stage2_manual_claims != "pass" or status.stage3_evidence_skeleton != "pass":
    return "blocked_prerequisites"
  if any(s in {"external_api_required", "query_plan_ready"} for s in stages):
    return "partial_external_api_pending"
  if any(s.startswith("blocked") for s in stages):
    return "blocked"
  return "in_progress"


def _inspect_seed_status(config: EndToEndChainConfig, publication_number: str) -> SeedChainStatus:
  root = _root(config)
  pub = str(publication_number).strip()
  s4, pdir = _stage4_status(root, pub)
  s5, wdir = _stage5_status(root, config.theme_id, pub)
  s6, ldir = _stage6_status(root, pub)
  s7, sdir = _stage7_status(root, pub)
  s8, digest_path = _stage8_status(root, pub)

  status = SeedChainStatus(
    publication_number=pub,
    stage2_manual_claims=_stage2_status(root, pub),
    stage3_evidence_skeleton=_stage3_status(root, pub),
    stage4_paper_candidates=s4,
    stage5_web_signals=s5,
    stage6_link_candidates=s6,
    stage7_strategic_watch=s7,
    stage8_digest=s8,
    overall_status="",
    next_action="",
    output_paths={
      "paper_candidates_dir": pdir,
      "web_signals_dir": wdir,
      "link_candidates_dir": ldir,
      "strategic_watch_dir": sdir,
      "digest_md": digest_path,
    },
    caveats=[CHAIN_CAUTION, PAPER_CAUTION, WEB_SIGNAL_CAUTION, LINK_CAUTION, WATCH_CAUTION],
  )
  status.overall_status = _compute_overall(status)
  status.next_action = _next_action_for_status(status)
  return status


def _next_action_for_status(status: SeedChainStatus) -> str:
  if status.stage2_manual_claims != "pass":
    return "Manual Claims を保存してください"
  if status.stage3_evidence_skeleton != "pass":
    return "Evidence Map skeleton を生成してください"
  if status.stage4_paper_candidates in {"external_api_required", "query_plan_ready"}:
    return "Paper Query Plan を作成するか、allow_external_api=true で Paper 候補を取得してください"
  if status.stage5_web_signals in {"external_api_required", "query_plan_ready"}:
    return "Web Signal Query Plan を作成するか、allow_external_api=true で Web Signal 候補を取得してください"
  if status.stage6_link_candidates.startswith("blocked"):
    return "Paper 候補と Web Signal 候補を取得してから Link Candidate を生成してください"
  if status.stage7_strategic_watch == "output_missing":
    return "Strategic Watch Brief を生成してください"
  if status.stage8_digest == "output_missing":
    return "Digest Preview を生成してください"
  return "End-to-End チェーン完了。レポートを保存してください"


def inspect_end_to_end_status(config: EndToEndChainConfig) -> EndToEndChainResult:
  statuses = [_inspect_seed_status(config, pub) for pub in config.publication_numbers]
  completed = sum(1 for s in statuses if s.overall_status == "complete")
  blocked = sum(1 for s in statuses if s.overall_status.startswith("blocked"))
  ext_req = sum(
    1
    for s in statuses
    if s.stage4_paper_candidates in {"external_api_required", "query_plan_ready"}
    or s.stage5_web_signals in {"external_api_required", "query_plan_ready"}
  )
  return EndToEndChainResult(
    theme_id=config.theme_id,
    created_at=_utc_now(),
    seed_statuses=statuses,
    completed_count=completed,
    blocked_count=blocked,
    external_api_required_count=ext_req,
    caveats=[CHAIN_CAUTION, DIGEST_CAUTION],
  )


def run_paper_candidate_step(
  config: EndToEndChainConfig,
  publication_number: str,
  *,
  query_plan_only: bool = False,
) -> SeedChainStatus:
  root = _root(config)
  pub = str(publication_number).strip()
  out_dir = paper_candidates_dir(root, pub)
  plan_payload = build_paper_query_plan_from_skeleton(pub, root)
  _save_paper_query_plan(plan_payload, out_dir)

  execute = (
    not query_plan_only
    and config.allow_external_api
    and config.run_openalex
    and not config.dry_run
  )

  if not execute:
    status = _inspect_seed_status(config, pub)
    status.stage4_paper_candidates = "query_plan_ready" if query_plan_only else "external_api_required"
    status.next_action = "allow_external_api=true かつ run_openalex=true で Paper 候補を取得できます"
    return status

  candidates = plan_payload.get("openalex_query_candidates") or []
  max_queries = min(3, max(1, config.max_papers // 2))
  oa_config = OpenAlexExecutionConfig(
    max_queries=max_queries,
    max_results_per_query=min(5, config.max_papers),
    cache_first=config.cache_first,
    execute_openalex=True,
    output_dir=str(out_dir),
  )
  result = execute_openalex_limited(candidates, oa_config, publication_number=pub)
  save_openalex_limited_artifacts(result, out_dir)

  claim_elements = _load_claim_elements(evidence_map_output_dir(root, pub))
  relevance = apply_relevance_to_paper_records(
    result.get("paper_records") or [],
    claim_elements,
    top_n=config.max_papers,
  )
  save_paper_candidate_relevance_artifacts(relevance, out_dir)

  if result.get("paper_records"):
    save_records_csv(result.get("paper_records") or [], out_dir / "paper_candidates.csv")

  summary_lines = [
    "# Paper Candidate Summary",
    "",
    f"- publication_number: {pub}",
    f"- executed: {result.get('executed_queries_count', 0)} queries",
    f"- paper_records: {result.get('total_paper_records', 0)}",
    f"- selected: {len(relevance.get('selected') or [])}",
    "",
    PAPER_CAUTION,
  ]
  (out_dir / "paper_candidate_summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

  status = _inspect_seed_status(config, pub)
  if result.get("total_paper_records", 0) > 0:
    status.stage4_paper_candidates = "pass"
  else:
    status.stage4_paper_candidates = "external_api_required"
  return status


def _build_web_signal_query_plan(
  config: EndToEndChainConfig,
  publication_number: str,
) -> dict[str, Any]:
  root = _root(config)
  pub = str(publication_number).strip()
  ev_dir = evidence_map_output_dir(root, pub)
  claim_elements = _load_claim_elements(ev_dir)
  paper_plan_path = paper_candidates_dir(root, pub) / "paper_query_plan.json"
  paper_plan = _load_json(paper_plan_path) if paper_plan_path.exists() else {}

  keywords: list[str] = []
  for row in claim_elements:
    for key in ("keywords", "material_terms", "process_terms", "property_terms"):
      raw = str(row.get(key) or "")
      keywords.extend([p.strip() for p in raw.split("|") if p.strip()])
  topic = config.theme_name or config.theme_id
  if keywords:
    topic = f"{topic} {' '.join(keywords[:3])}"

  return {
    "publication_number": pub,
    "theme_id": config.theme_id,
    "topic": topic,
    "categories": ["national_project", "money", "ir_disclosure", "company", "market"],
    "languages": ["ja", "en"],
    "max_queries": config.max_web_signals,
    "claim_element_count": len(claim_elements),
    "paper_query_plan_ref": str(paper_plan_path),
    "caveats": [WEB_SIGNAL_CAUTION],
    "notes": "Web signal query plan. Tavily execution requires allow_external_api=true.",
  }


def run_web_signal_candidate_step(
  config: EndToEndChainConfig,
  publication_number: str,
  *,
  query_plan_only: bool = False,
) -> SeedChainStatus:
  root = _root(config)
  pub = str(publication_number).strip()
  out_dir = web_signals_dir(root, config.theme_id, pub)
  out_dir.mkdir(parents=True, exist_ok=True)

  plan = _build_web_signal_query_plan(config, pub)
  (out_dir / "web_signal_query_plan.json").write_text(
    json.dumps(plan, indent=2, ensure_ascii=False),
    encoding="utf-8",
  )

  execute = (
    not query_plan_only
    and config.allow_external_api
    and config.run_tavily
    and not config.dry_run
  )

  if not execute:
    status = _inspect_seed_status(config, pub)
    status.stage5_web_signals = "query_plan_ready" if query_plan_only else "external_api_required"
    status.next_action = "allow_external_api=true かつ run_tavily=true で Web Signal 候補を取得できます"
    return status

  if not get_tavily_api_key():
    status = _inspect_seed_status(config, pub)
    status.stage5_web_signals = "blocked_missing_tavily_config"
    status.next_action = "TAVILY_API_KEY を設定するか query_plan_only で進めてください"
    return status

  tavily_config = TavilyRunConfig(
    topic=str(plan.get("topic") or config.theme_name),
    categories=list(plan.get("categories") or ["national_project", "money", "company"]),
    languages=["ja", "en"],
    max_queries=min(config.max_web_signals, 10),
    max_results_per_query=5,
    output_dir=str(out_dir),
    dry_run=False,
    plan_only=False,
    execute_tavily=True,
    build_review_pack=True,
    review_keywords=None,
  )
  pipeline_result = run_tavily_web_signal_pipeline(tavily_config)
  summary_lines = [
    "# Web Signal Summary",
    "",
    f"- publication_number: {pub}",
    f"- status: {pipeline_result.get('status')}",
    f"- signal_count: {pipeline_result.get('signal_count', 0)}",
    "",
    WEB_SIGNAL_CAUTION,
  ]
  (out_dir / "web_signal_summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

  status = _inspect_seed_status(config, pub)
  if pipeline_result.get("status") == "blocked_missing_api_key":
    status.stage5_web_signals = "blocked_missing_tavily_config"
  elif (out_dir / "web_signals.csv").exists() or (out_dir / "review_pack").exists():
    status.stage5_web_signals = "pass"
  else:
    status.stage5_web_signals = "external_api_required"
  return status


def _ensure_evidence_map_items(root: Path, pub: str) -> None:
  ev_dir = evidence_map_output_dir(root, pub)
  items_path = ev_dir / "evidence_map_items.csv"
  claim_path = ev_dir / "claim_elements.csv"
  if items_path.exists() or not claim_path.exists():
    return
  rows = load_records_csv(str(claim_path))
  mapped: list[dict[str, str]] = []
  for row in rows:
    mapped.append(
      {
        "claim_element_id": str(row.get("element_id") or ""),
        "claim_element_text": str(row.get("element_text") or ""),
        "claim_number": str(row.get("claim_number") or ""),
        "publication_number": pub,
      },
    )
  save_records_csv(mapped, items_path)


def _paper_data_ready(root: Path, pub: str) -> bool:
  pdir = paper_candidates_dir(root, pub)
  return (pdir / "selected_evidence_papers.csv").exists() or (pdir / "paper_candidates.csv").exists()


def _web_data_ready(root: Path, theme_id: str, pub: str) -> bool:
  wdir = web_signals_dir(root, theme_id, pub)
  return (wdir / "web_signals.csv").exists() or (wdir / "review_pack" / "high_priority_web_signals.csv").exists()


def run_link_candidate_step(
  config: EndToEndChainConfig,
  publication_number: str,
) -> SeedChainStatus:
  root = _root(config)
  pub = str(publication_number).strip()
  _ensure_evidence_map_items(root, pub)

  paper_ready = _paper_data_ready(root, pub)
  web_ready = _web_data_ready(root, config.theme_id, pub)
  pdir = paper_candidates_dir(root, pub)
  wdir = web_signals_dir(root, config.theme_id, pub)
  only_plan_paper = (pdir / "paper_query_plan.json").exists() and not paper_ready
  only_plan_web = (wdir / "web_signal_query_plan.json").exists() and not web_ready

  status = _inspect_seed_status(config, pub)
  if only_plan_paper and only_plan_web:
    status.stage6_link_candidates = "blocked_missing_paper_or_web_signal"
    status.next_action = "Paper/Web の query_plan のみでは Link 生成不可。外部API実行後に再試行してください"
    return status
  if only_plan_paper:
    status.stage6_link_candidates = "paper_link_missing"
    status.next_action = "Paper 候補 CSV を取得してから Link Candidate を生成してください"
    return status
  if only_plan_web:
    status.stage6_link_candidates = "web_signal_missing"
    status.next_action = "Web Signal 候補を取得してから Link Candidate を生成してください"
    return status
  if not web_ready:
    status.stage6_link_candidates = "web_signal_missing"
    return status

  scoring = LinkScoringConfig(calibrated_scoring=True)
  pack = build_web_signal_link_pack(
    publication_number=pub,
    project_root=root,
    web_signal_review_dir=str(wdir / "review_pack"),
    evidence_map_dir=str(evidence_map_output_dir(root, pub)),
    openalex_dir=str(pdir),
    scoring_config=scoring,
  )
  out_dir = link_candidates_dir(root, pub)
  save_web_signal_link_pack(pack, out_dir, scoring_config=scoring)

  scores = [item.link_score for item in pack.link_candidates]
  dist: dict[str, int] = {}
  for score in scores:
    bucket = f"{(score // 10) * 10}-{(score // 10) * 10 + 9}"
    dist[bucket] = dist.get(bucket, 0) + 1
  summary_md = out_dir / "patent_paper_web_signal_summary.md"
  extra = [
    "",
    "## Score distribution",
    "",
    json.dumps(dist, ensure_ascii=False),
    "",
    LINK_CAUTION,
  ]
  if summary_md.exists():
    summary_md.write_text(summary_md.read_text(encoding="utf-8") + "\n".join(extra), encoding="utf-8")

  status = _inspect_seed_status(config, pub)
  if pack.link_candidates:
    status.stage6_link_candidates = "pass"
  else:
    status.stage6_link_candidates = "blocked_missing_paper_or_web_signal"
  return status


def run_strategic_watch_step(
  config: EndToEndChainConfig,
  publication_number: str,
) -> SeedChainStatus:
  root = _root(config)
  pub = str(publication_number).strip()
  paper_ready = _paper_data_ready(root, pub)
  web_ready = _web_data_ready(root, config.theme_id, pub)
  limited = not (paper_ready and web_ready)

  brief = build_strategic_watch_brief(
    pub,
    project_root=root,
    web_signal_link_dir=link_candidates_dir(root, pub),
  )
  if limited:
    brief.executive_summary = (
      "Paper/Web evidence is incomplete. This is a limited_watch_brief for monitoring candidates only."
    )
    brief.caveats = list(brief.caveats or []) + [
      "Paper/Web evidence is incomplete.",
      WATCH_CAUTION,
    ]
  out_dir = strategic_watch_dir(root, pub)
  paths = save_strategic_watch_brief(brief, out_dir)
  brief_json = _load_json(paths["strategic_watch_brief_json"]) or {}
  if limited:
    brief_json["limited_watch_brief"] = True
    paths["strategic_watch_brief_json"].write_text(
      json.dumps(brief_json, indent=2, ensure_ascii=False),
      encoding="utf-8",
    )

  status = _inspect_seed_status(config, pub)
  status.stage7_strategic_watch = "limited_watch_brief" if limited else "pass"
  status.output_paths.update({k: str(v) for k, v in paths.items()})
  return status


def _build_jp_seed_digest_markdown(status: SeedChainStatus, config: EndToEndChainConfig) -> str:
  lines = [
    "# JP Seed Validation Digest (preview only)",
    "",
    f"- publication_number: {status.publication_number}",
    f"- theme: {config.theme_name} (`{config.theme_id}`)",
    f"- created_at: {_utc_now()}",
    "",
    "## Stage status",
    "",
    f"- Manual Claims (Stage 2): {status.stage2_manual_claims}",
    f"- Evidence Map skeleton (Stage 3): {status.stage3_evidence_skeleton}",
    f"- Paper candidates (Stage 4): {status.stage4_paper_candidates}",
    f"- Web signals (Stage 5): {status.stage5_web_signals}",
    f"- Link candidates (Stage 6): {status.stage6_link_candidates}",
    f"- Strategic Watch (Stage 7): {status.stage7_strategic_watch}",
    f"- Digest (Stage 8): pass (this file)",
    "",
    "## Evidence gaps / Next actions",
    "",
    f"- {status.next_action}",
    "",
    "## Caveats",
    "",
  ]
  for caveat in status.caveats + [DIGEST_CAUTION, CHAIN_CAUTION]:
    lines.append(f"- {caveat}")
  return "\n".join(lines)


def run_digest_step(
  config: EndToEndChainConfig,
  publication_number: str,
) -> SeedChainStatus:
  root = _root(config)
  pub = str(publication_number).strip()
  status = _inspect_seed_status(config, pub)
  delivery_dir = root / "outputs" / "delivery"
  delivery_dir.mkdir(parents=True, exist_ok=True)

  md_path = delivery_dir / f"jp_seed_digest_{pub}.md"
  html_path = delivery_dir / f"jp_seed_digest_{pub}.html"
  diff_path = delivery_dir / f"jp_seed_digest_diff_{pub}.md"

  body = _build_jp_seed_digest_markdown(status, config)
  if (strategic_watch_dir(root, pub) / "strategic_watch_items.csv").exists():
    try:
      digest: WeeklyDigest = build_weekly_digest(pub, root, mode="preview", send_status="preview_only")
      body = (
        "# JP Seed Validation Digest (preview only)\n\n"
        f"**件名:** JP Seed Validation Digest — {pub}\n\n"
        f"{digest.markdown_body}\n\n"
        f"---\n\n{DIGEST_CAUTION}\n"
      )
    except Exception:  # noqa: BLE001 — fallback to simple digest
      pass

  md_path.write_text(body, encoding="utf-8")
  html_body = "<html><body><pre>" + body.replace("<", "&lt;").replace(">", "&gt;") + "</pre></body></html>"
  html_path.write_text(html_body, encoding="utf-8")

  try:
    snapshot = build_digest_snapshot(root, pub)
    diff = compare_digest_snapshots(None, snapshot)
    diff_text = diff.diff_markdown or "# JP Seed Digest Diff\n\n- First snapshot (no prior digest).\n"
  except Exception:  # noqa: BLE001
    diff_text = "# JP Seed Digest Diff\n\n- First snapshot (no prior digest).\n"
  diff_path.write_text(diff_text, encoding="utf-8")

  status.stage8_digest = "pass"
  status.output_paths["jp_seed_digest_md"] = str(md_path)
  status.output_paths["jp_seed_digest_html"] = str(html_path)
  status.output_paths["jp_seed_digest_diff_md"] = str(diff_path)
  status.overall_status = _compute_overall(status)
  return status


STEP_RUNNERS = {
  "paper_query_plan": lambda c, p: run_paper_candidate_step(c, p, query_plan_only=True),
  "paper_candidates": lambda c, p: run_paper_candidate_step(c, p, query_plan_only=False),
  "web_signal_query_plan": lambda c, p: run_web_signal_candidate_step(c, p, query_plan_only=True),
  "web_signals": lambda c, p: run_web_signal_candidate_step(c, p, query_plan_only=False),
  "link_candidates": run_link_candidate_step,
  "strategic_watch": run_strategic_watch_step,
  "digest": run_digest_step,
}


def run_selected_chain_steps(
  config: EndToEndChainConfig,
  selected_steps: list[str],
) -> EndToEndChainResult:
  for step in selected_steps:
    runner = STEP_RUNNERS.get(step)
    if runner is None:
      continue
    for pub in config.publication_numbers:
      runner(config, pub)
  return inspect_end_to_end_status(config)


def render_end_to_end_chain_markdown(result: EndToEndChainResult) -> str:
  lines = [
    "# End-to-End Chain Summary (Phase 24.4C)",
    "",
    f"- theme_id: `{result.theme_id}`",
    f"- created_at: {result.created_at}",
    f"- completed: {result.completed_count}",
    f"- blocked: {result.blocked_count}",
    f"- external_api_required: {result.external_api_required_count}",
    "",
    "| publication_number | Stage2 | Stage3 | Stage4 | Stage5 | Stage6 | Stage7 | Stage8 | overall | next_action |",
    "|---|---|---|---|---|---|---|---|---|---|",
  ]
  for seed in result.seed_statuses:
    lines.append(
      f"| {seed.publication_number} | {seed.stage2_manual_claims} | {seed.stage3_evidence_skeleton} "
      f"| {seed.stage4_paper_candidates} | {seed.stage5_web_signals} | {seed.stage6_link_candidates} "
      f"| {seed.stage7_strategic_watch} | {seed.stage8_digest} | {seed.overall_status} | {seed.next_action} |",
    )
  lines.extend(["", "## Caveats", ""])
  for caveat in result.caveats:
    lines.append(f"- {caveat}")
  lines.extend(
    [
      "",
      "## 注意",
      "",
      "- Evidence Map skeleton は最終 Evidence Map ではありません。",
      "- OpenAlex/Tavily は allow_external_api=true の明示同意時のみ実行します。",
      "- UI からメール送信・scheduler 登録は行いません。",
      f"- {CHAIN_CAUTION}",
      "",
    ],
  )
  return "\n".join(lines)


def save_end_to_end_chain_result(
  result: EndToEndChainResult,
  output_dir: Path | str,
) -> dict[str, Path]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  paths = {
    "end_to_end_chain_summary_md": out / "end_to_end_chain_summary.md",
    "end_to_end_chain_summary_json": out / "end_to_end_chain_summary.json",
    "seed_chain_status_csv": out / "seed_chain_status.csv",
    "next_actions_md": out / "next_actions.md",
  }
  paths["end_to_end_chain_summary_md"].write_text(
    render_end_to_end_chain_markdown(result),
    encoding="utf-8",
  )
  paths["end_to_end_chain_summary_json"].write_text(
    json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
    encoding="utf-8",
  )

  rows = [s.to_dict() for s in result.seed_statuses]
  if rows:
    df = pd.DataFrame(rows)
    df.to_csv(paths["seed_chain_status_csv"], index=False, encoding="utf-8")
  else:
    paths["seed_chain_status_csv"].write_text("", encoding="utf-8")

  next_lines = ["# Next Actions", ""]
  for seed in result.seed_statuses:
    next_lines.append(f"- **{seed.publication_number}**: {seed.next_action}")
  next_lines.extend(["", CHAIN_CAUTION, ""])
  paths["next_actions_md"].write_text("\n".join(next_lines), encoding="utf-8")

  result.output_paths = {k: str(v) for k, v in paths.items()}
  return paths
