"""Cross-theme validation smoke and user theme validation UI (Phase 24.4 / 24.4A)."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from tech_cartography.validation.core_validation import (
  VALIDATION_CAUTION,
  analyze_link_score_calibration,
  build_reproducibility_patent_status,
)
from tech_cartography.validation.reproducibility_smoke import detect_artifact_flags

StageStatus = Literal[
  "pass",
  "blocked",
  "not_run",
  "manual_input_required",
  "external_api_required",
  "external_search_not_configured",
  "output_missing",
  "failed",
]

STAGE_NAMES = (
  "theme_config_loaded",
  "seed_patents_available",
  "fulltext_or_manual_claims_available",
  "evidence_map_available_or_buildable",
  "paper_candidates_available",
  "web_signal_candidates_available",
  "link_candidates_available",
  "strategic_watch_available",
  "digest_available",
)

UI_STAGE_NAMES = (
  "theme_config_loaded",
  "search_plan_created",
  "patent_candidates_available",
  "fulltext_or_manual_claims_available",
  "evidence_map_available_or_buildable",
  "paper_candidates_available",
  "web_signal_candidates_available",
  "link_candidates_available",
  "strategic_watch_available",
  "digest_available",
)

THEME_VALIDATION_SAFETY_MESSAGES = (
  "この検証UIは、別テーマでもTech Cartographyの流れが動くか確認するためのものです。",
  "入力キーワードに社外秘・未公開情報を入れないでください。",
  "外部検索を実行する場合、入力したキーワードが外部APIまたはBigQueryに送信される可能性があります。",
  "Webシグナル・論文候補・Link Candidateは確認候補であり、最終結論ではありません。",
  "本ツールはFTO調査、侵害判断、有効性判断、法的見解には使用しないでください。",
)


@dataclass
class ThemeValidationCase:
  theme_id: str
  theme_name: str
  description: str
  core_keywords: list[str]
  application_keywords: list[str]
  material_or_process_keywords: list[str]
  exclude_keywords: list[str]
  seed_publication_numbers: list[str]
  validation_goal: str

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> ThemeValidationCase:
    return cls(
      theme_id=str(data.get("theme_id", "")).strip(),
      theme_name=str(data.get("theme_name", "")).strip(),
      description=str(data.get("description", "")).strip(),
      core_keywords=[str(v) for v in data.get("core_keywords", []) if str(v).strip()],
      application_keywords=[str(v) for v in data.get("application_keywords", []) if str(v).strip()],
      material_or_process_keywords=[
        str(v) for v in data.get("material_or_process_keywords", []) if str(v).strip()
      ],
      exclude_keywords=[str(v) for v in data.get("exclude_keywords", []) if str(v).strip()],
      seed_publication_numbers=[
        str(v).strip() for v in data.get("seed_publication_numbers", []) if str(v).strip()
      ],
      validation_goal=str(data.get("validation_goal", "")).strip(),
    )

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class ThemeStageResult:
  stage_id: int
  stage_name: str
  status: str
  message: str

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class ThemeValidationResult:
  theme_id: str
  theme_name: str
  publication_number: str | None
  dry_run: bool
  no_external_api: bool
  stages: list[ThemeStageResult] = field(default_factory=list)
  overall_status: str = "not_run"
  caveat: str = VALIDATION_CAUTION

  def to_dict(self) -> dict[str, Any]:
    data = asdict(self)
    data["stages"] = [stage.to_dict() for stage in self.stages]
    return data


@dataclass
class ThemeValidationStage:
  stage: str
  status: str
  reason: str
  next_action: str
  output_path: str

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class ThemeValidationRunResult:
  theme_id: str
  created_at: str
  mode: str
  case: ThemeValidationCase
  stages: list[ThemeValidationStage] = field(default_factory=list)
  search_queries: list[str] = field(default_factory=list)
  patent_candidates: list[dict[str, Any]] = field(default_factory=list)
  warnings: list[str] = field(default_factory=list)
  output_paths: dict[str, str] = field(default_factory=dict)

  def to_dict(self) -> dict[str, Any]:
    return {
      "theme_id": self.theme_id,
      "created_at": self.created_at,
      "mode": self.mode,
      "case": self.case.to_dict(),
      "stages": [stage.to_dict() for stage in self.stages],
      "search_queries": self.search_queries,
      "patent_candidates": self.patent_candidates,
      "warnings": self.warnings,
      "output_paths": self.output_paths,
    }


def load_theme_validation_config(path: Path | str) -> list[ThemeValidationCase]:
  config_path = Path(path)
  data = json.loads(config_path.read_text(encoding="utf-8"))
  cases = data.get("cases", data if isinstance(data, list) else [])
  return [ThemeValidationCase.from_dict(item) for item in cases]


def find_theme_case(cases: list[ThemeValidationCase], theme_id: str) -> ThemeValidationCase | None:
  target = str(theme_id).strip()
  for case in cases:
    if case.theme_id == target:
      return case
  return None


def _manual_exists(project_root: Path, publication_number: str) -> bool:
  claims = project_root / "inputs" / "manual" / f"{publication_number}_claims.txt"
  manual_json = project_root / "outputs" / "manual_fulltext_inputs" / f"{publication_number}.json"
  return claims.exists() or manual_json.exists()


def _web_signals_exist(project_root: Path) -> bool:
  review = (
    project_root
    / "outputs"
    / "web_signals"
    / "tavily_pan_carbon_fiber"
    / "review_pack"
    / "high_priority_web_signals.csv"
  )
  return review.exists()


def evaluate_theme_validation_stages(
  *,
  project_root: Path | str,
  theme_case: ThemeValidationCase,
  publication_number: str | None = None,
  manual_claims_path: Path | str | None = None,
  dry_run: bool = False,
  no_external_api: bool = True,
) -> list[ThemeStageResult]:
  root = Path(project_root)
  pub = publication_number or (theme_case.seed_publication_numbers[0] if theme_case.seed_publication_numbers else None)
  stages: list[ThemeStageResult] = []

  stages.append(
    ThemeStageResult(
      stage_id=0,
      stage_name=STAGE_NAMES[0],
      status="pass",
      message=f"theme_config_loaded: {theme_case.theme_id}",
    ),
  )

  if not theme_case.seed_publication_numbers and not pub:
    stages.append(
      ThemeStageResult(
        stage_id=1,
        stage_name=STAGE_NAMES[1],
        status="blocked",
        message="seed_publication_numbers が未設定です。",
      ),
    )
    return stages

  seed_pubs = theme_case.seed_publication_numbers or ([pub] if pub else [])
  seed_ready = any(
    (root / "outputs" / "evidence_map_synthesis" / seed_pub).exists()
    or _manual_exists(root, seed_pub)
    for seed_pub in seed_pubs
  )
  stages.append(
    ThemeStageResult(
      stage_id=1,
      stage_name=STAGE_NAMES[1],
      status="pass" if seed_ready else "blocked",
      message="seed patent artifacts or manual inputs detected" if seed_ready else "seed patents not available",
    ),
  )

  if not pub:
    for index in range(2, len(STAGE_NAMES)):
      stages.append(
        ThemeStageResult(
          stage_id=index,
          stage_name=STAGE_NAMES[index],
          status="not_run",
          message="publication_number 未指定のため未評価",
        ),
      )
    return stages

  manual_path = Path(manual_claims_path) if manual_claims_path else None
  manual_ok = _manual_exists(root, pub) or (manual_path is not None and manual_path.exists())
  stages.append(
    ThemeStageResult(
      stage_id=2,
      stage_name=STAGE_NAMES[2],
      status="pass" if manual_ok else "manual_input_required",
      message="manual claims/fulltext available" if manual_ok else "manual claims required",
    ),
  )

  flags = detect_artifact_flags(root, pub)
  if flags.get("evidence_map_exists"):
    ev_status: str = "pass"
    ev_msg = "evidence map exists"
  elif manual_ok:
    ev_status = "blocked" if dry_run or no_external_api else "external_api_required"
    ev_msg = "manual claims exist; evidence map build requires pipeline run (not executed in no-external-api mode)"
  else:
    ev_status = "blocked"
    ev_msg = "blocked: manual claims and evidence map both missing"

  stages.append(ThemeStageResult(stage_id=3, stage_name=STAGE_NAMES[3], status=ev_status, message=ev_msg))

  papers_ok = bool(flags.get("selected_evidence_papers_exists"))
  stages.append(
    ThemeStageResult(
      stage_id=4,
      stage_name=STAGE_NAMES[4],
      status="pass" if papers_ok else ("external_api_required" if no_external_api else "blocked"),
      message="paper candidates available" if papers_ok else "paper candidates require OpenAlex execution",
    ),
  )

  web_ok = _web_signals_exist(project_root=root)
  stages.append(
    ThemeStageResult(
      stage_id=5,
      stage_name=STAGE_NAMES[5],
      status="pass" if web_ok else ("external_api_required" if no_external_api else "blocked"),
      message="web signal candidates available" if web_ok else "web signals require Tavily execution",
    ),
  )

  link_path = root / "outputs" / "web_signal_links" / pub / "web_signal_link_candidates.csv"
  link_ok = link_path.exists()
  stages.append(
    ThemeStageResult(
      stage_id=6,
      stage_name=STAGE_NAMES[6],
      status="pass" if link_ok else "blocked",
      message="link candidates available" if link_ok else "link candidates not built for publication",
    ),
  )

  watch_path = root / "outputs" / "strategic_watch_briefs" / pub / "strategic_watch_brief.md"
  watch_ok = watch_path.exists()
  stages.append(
    ThemeStageResult(
      stage_id=7,
      stage_name=STAGE_NAMES[7],
      status="pass" if watch_ok else "blocked",
      message="strategic watch brief available" if watch_ok else "strategic watch not built",
    ),
  )

  digest_path = root / "outputs" / "delivery" / f"weekly_digest_preview_{pub}.md"
  digest_ok = digest_path.exists()
  stages.append(
    ThemeStageResult(
      stage_id=8,
      stage_name=STAGE_NAMES[8],
      status="pass" if digest_ok else "not_run",
      message="weekly digest available" if digest_ok else "digest not generated (delivery optional)",
    ),
  )

  return stages


def run_theme_validation_smoke(
  *,
  project_root: Path | str,
  theme_case: ThemeValidationCase,
  publication_number: str | None = None,
  manual_claims_path: Path | str | None = None,
  dry_run: bool = False,
  no_external_api: bool = True,
  seed_only: bool = False,
) -> ThemeValidationResult:
  pub = publication_number
  if seed_only and theme_case.seed_publication_numbers:
    pub = theme_case.seed_publication_numbers[0]

  stages = evaluate_theme_validation_stages(
    project_root=project_root,
    theme_case=theme_case,
    publication_number=pub,
    manual_claims_path=manual_claims_path,
    dry_run=dry_run,
    no_external_api=no_external_api,
  )

  if seed_only:
    stages = [stage for stage in stages if stage.stage_id <= 1]

  statuses = {stage.status for stage in stages}
  if "failed" in statuses:
    overall = "failed"
  elif "blocked" in statuses or "manual_input_required" in statuses:
    overall = "blocked"
  elif all(stage.status in {"pass", "not_run"} for stage in stages):
    overall = "pass"
  else:
    overall = "not_run"

  return ThemeValidationResult(
    theme_id=theme_case.theme_id,
    theme_name=theme_case.theme_name,
    publication_number=pub,
    dry_run=dry_run,
    no_external_api=no_external_api,
    stages=stages,
    overall_status=overall,
  )


def render_theme_validation_md(result: ThemeValidationResult, *, project_root: Path | str = ".") -> str:
  root = Path(project_root)
  lines = [
    f"# Theme Validation Report: {result.theme_id}",
    "",
    f"- theme_name: {result.theme_name}",
    f"- publication_number: {result.publication_number or '（なし）'}",
    f"- dry_run: {result.dry_run}",
    f"- no_external_api: {result.no_external_api}",
    f"- overall_status: **{result.overall_status}**",
    "",
    "## Stage matrix",
    "",
    "| stage | name | status | message |",
    "|---:|---|---|---|",
  ]
  for stage in result.stages:
    lines.append(f"| {stage.stage_id} | {stage.stage_name} | {stage.status} | {stage.message} |")

  if result.publication_number:
    repro = build_reproducibility_patent_status(root, result.publication_number)
    cal = analyze_link_score_calibration(root, result.publication_number)
    lines.extend(["", "## Reference checks", ""])
    lines.append(f"- reproducibility_status: {repro.status}")
    if cal:
      lines.append(f"- link all_100_problem_resolved: {cal.all_100_problem_resolved}")

  lines.extend(["", "## 注意", "", f"- {result.caveat}", ""])
  return "\n".join(lines)


def parse_keyword_text(text: str) -> list[str]:
  """Parse comma- or newline-separated keywords into a normalized list."""
  if not text or not str(text).strip():
    return []
  parts = re.split(r"[,;\n]+", str(text))
  seen: set[str] = set()
  out: list[str] = []
  for part in parts:
    token = part.strip()
    if not token:
      continue
    key = token.lower()
    if key in seen:
      continue
    seen.add(key)
    out.append(token)
  return out


def slugify_theme_id(theme_name: str, *, fallback: str = "custom_theme") -> str:
  slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(theme_name or "").strip().lower()).strip("_")
  return slug or fallback


def build_theme_search_queries(case: ThemeValidationCase) -> list[str]:
  """Build search query drafts from theme keywords (no external API)."""
  core = list(case.core_keywords)
  material = list(case.material_or_process_keywords)
  application = list(case.application_keywords)
  exclude = list(case.exclude_keywords)

  queries: list[str] = []
  if core:
    queries.append(" AND ".join(core[:4]))
  if material:
    queries.append(f"({' OR '.join(material[:3])})")
  if application:
    queries.append(f"application: {' OR '.join(application[:3])}")
  if core and application:
    queries.append(f"{core[0]} AND ({' OR '.join(application[:2])})")
  if core and material:
    queries.append(f"{core[0]} AND ({' OR '.join(material[:2])})")
  if exclude:
    queries.append(f"exclude: {' OR '.join(exclude[:3])}")

  deduped: list[str] = []
  seen: set[str] = set()
  for query in queries:
    key = query.lower()
    if key in seen:
      continue
    seen.add(key)
    deduped.append(query)
  return deduped


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ui_stage(
  stage: str,
  *,
  status: str,
  reason: str,
  next_action: str = "",
  output_path: str = "",
) -> ThemeValidationStage:
  return ThemeValidationStage(
    stage=stage,
    status=status,
    reason=reason,
    next_action=next_action,
    output_path=output_path,
  )


def _not_run_stages(start_index: int, reason: str) -> list[ThemeValidationStage]:
  return [
    _ui_stage(
      UI_STAGE_NAMES[index],
      status="not_run",
      reason=reason,
      next_action="前段階を完了するか、既存outputs検証を実行してください。",
    )
    for index in range(start_index, len(UI_STAGE_NAMES))
  ]


def _artifact_path(root: Path, template: str, publication_number: str) -> Path:
  return root / template.format(publication_number=publication_number)


EXISTING_OUTPUT_CHECKS: tuple[tuple[str, str, str, str], ...] = (
  (
    "fulltext_or_manual_claims_available",
    "outputs/manual_fulltext_inputs/{publication_number}.json",
    "manual_input_required",
    "Manual Claims JSON を inputs/manual または outputs/manual_fulltext_inputs に用意してください。",
  ),
  (
    "evidence_map_available_or_buildable",
    "outputs/evidence_map_synthesis/{publication_number}/evidence_map_synthesis.json",
    "output_missing",
    "Evidence Map を生成するか、既存成果物を outputs に配置してください。",
  ),
  (
    "paper_candidates_available",
    "outputs/openalex_limited_execution/selected_evidence_papers.csv",
    "output_missing",
    "論文候補は OpenAlex 実行後に outputs に保存されます（本UIでは自動実行しません）。",
  ),
  (
    "web_signal_candidates_available",
    "outputs/web_signal_links/{publication_number}/web_signal_link_candidates.csv",
    "output_missing",
    "Web Signal 候補 CSV を outputs/web_signal_links に配置するか、パイプラインを実行してください。",
  ),
  (
    "link_candidates_available",
    "outputs/web_signal_links/{publication_number}/web_signal_link_candidates.csv",
    "output_missing",
    "Link Candidate CSV が未生成です。",
  ),
  (
    "strategic_watch_available",
    "outputs/strategic_watch_briefs/{publication_number}/strategic_watch_brief.json",
    "output_missing",
    "Strategic Watch brief JSON を outputs に配置してください。",
  ),
  (
    "digest_available",
    "outputs/delivery/weekly_digest_preview_{publication_number}.md",
    "output_missing",
    "週次ダイジェスト preview を delivery 出力から確認してください。",
  ),
)


def _check_patent_candidates(root: Path, seed_pubs: list[str]) -> ThemeValidationStage:
  candidates: list[Path] = []
  for pattern in (
    "outputs/bigquery_light_retrieval/**/bigquery_light_results.csv",
    "outputs/**/ranked_patents.csv",
    "outputs/**/top20_patents.csv",
  ):
    candidates.extend(root.glob(pattern))

  if candidates:
    first = sorted(candidates)[0]
    return _ui_stage(
      "patent_candidates_available",
      status="pass",
      reason="既存の特許候補 CSV を検出しました。",
      next_action="候補一覧を確認し、seed publication を選定してください。",
      output_path=str(first),
    )

  if seed_pubs:
    return _ui_stage(
      "patent_candidates_available",
      status="output_missing",
      reason="seed publication は指定されていますが、特許候補 CSV が見つかりません。",
      next_action="外部検索（同意後）または手動で seed を固定して次段階へ進めてください。",
      output_path="",
    )

  return _ui_stage(
    "patent_candidates_available",
    status="not_run",
    reason="特許候補の検索は未実行です。",
    next_action="検索計画を確認後、必要なら外部検索（同意後）を実行してください。",
    output_path="",
  )


def evaluate_existing_output_stages(
  *,
  project_root: Path | str,
  case: ThemeValidationCase,
  search_queries: list[str] | None = None,
) -> list[ThemeValidationStage]:
  root = Path(project_root)
  queries = search_queries or build_theme_search_queries(case)
  seed_pubs = list(case.seed_publication_numbers)
  primary_pub = seed_pubs[0] if seed_pubs else ""

  stages: list[ThemeValidationStage] = [
    _ui_stage(
      "theme_config_loaded",
      status="pass",
      reason=f"テーマ設定を読み込みました: {case.theme_name}",
      next_action="検索計画の dry-run または既存 outputs 検証を続行してください。",
    ),
    _ui_stage(
      "search_plan_created",
      status="pass" if queries else "blocked",
      reason="検索クエリ案を生成しました。" if queries else "キーワードが不足しています。",
      next_action="コアキーワードを追加して検索計画を再作成してください。",
    ),
    _check_patent_candidates(root, seed_pubs),
  ]

  if not primary_pub:
    stages.extend(
      _not_run_stages(3, "seed publication number が未指定のため、以降の成果物検査は未実行です。"),
    )
    return stages

  for stage_name, rel_template, missing_status, next_action in EXISTING_OUTPUT_CHECKS:
    rel_path = rel_template.format(publication_number=primary_pub)
    path = root / rel_path
    if path.exists():
      stages.append(
        _ui_stage(
          stage_name,
          status="pass",
          reason="既存 outputs を検出しました。",
          next_action="成果物を開いて内容を確認してください。",
          output_path=str(path),
        ),
      )
      continue

    manual_template = root / "outputs" / "manual_fulltext_inputs" / f"{primary_pub}.template.json"
    if stage_name == "fulltext_or_manual_claims_available" and manual_template.exists():
      stages.append(
        _ui_stage(
          stage_name,
          status="manual_input_required",
          reason="Manual Claims テンプレートがあります。Claims を貼り付けて .json として保存してください。",
          next_action=f"{manual_template} を編集し {primary_pub}.json として保存してください。",
          output_path=str(manual_template),
        ),
      )
      continue

    legacy_claims = root / "inputs" / "manual" / f"{primary_pub}_claims.txt"
    if stage_name == "fulltext_or_manual_claims_available" and legacy_claims.exists():
      stages.append(
        _ui_stage(
          stage_name,
          status="pass",
          reason="legacy manual claims テキストを検出しました。",
          next_action="必要に応じて JSON 形式へ移行してください。",
          output_path=str(legacy_claims),
        ),
      )
      continue

    stages.append(
      _ui_stage(
        stage_name,
        status=missing_status,
        reason=f"成果物が見つかりません: {rel_path}",
        next_action=next_action,
        output_path=str(path),
      ),
    )

  return stages


def run_theme_validation_dry_run(case: ThemeValidationCase) -> ThemeValidationRunResult:
  queries = build_theme_search_queries(case)
  stages: list[ThemeValidationStage] = [
    _ui_stage(
      "theme_config_loaded",
      status="pass",
      reason=f"テーマ設定を読み込みました: {case.theme_name}",
      next_action="検索計画 dry-run の結果を確認してください。",
    ),
    _ui_stage(
      "search_plan_created",
      status="pass" if queries else "blocked",
      reason="検索クエリ案を生成しました（外部API未実行）。" if queries else "キーワード不足のため検索計画を作成できません。",
      next_action="キーワードを追加するか、既存 outputs 検証へ進んでください。",
    ),
  ]
  stages.extend(_not_run_stages(2, "dry-run のため Stage 2 以降は未実行です。"))

  warnings = [
    "外部API未実行: この dry-run はローカルで検索計画のみ作成します。",
    *THEME_VALIDATION_SAFETY_MESSAGES[1:2],
  ]
  return ThemeValidationRunResult(
    theme_id=case.theme_id,
    created_at=_utc_now_iso(),
    mode="dry_run",
    case=case,
    stages=stages,
    search_queries=queries,
    warnings=warnings,
  )


def run_existing_outputs_validation(
  case: ThemeValidationCase,
  output_dir: Path | str,
  *,
  search_queries: list[str] | None = None,
) -> ThemeValidationRunResult:
  root = Path(output_dir)
  queries = search_queries or build_theme_search_queries(case)
  stages = evaluate_existing_output_stages(
    project_root=root,
    case=case,
    search_queries=queries,
  )
  warnings = [
    "外部API未実行: 既存 outputs の存在確認のみ行いました。",
    *THEME_VALIDATION_SAFETY_MESSAGES[3:4],
  ]
  return ThemeValidationRunResult(
    theme_id=case.theme_id,
    created_at=_utc_now_iso(),
    mode="existing_outputs",
    case=case,
    stages=stages,
    search_queries=queries,
    warnings=warnings,
  )


def _build_query_plan_from_case(case: ThemeValidationCase, *, max_results: int) -> Any:
  from tech_cartography.strategy.query_plan import QueryPlan

  must_have = list(case.core_keywords[:3])
  should_have = list(case.material_or_process_keywords[:3] + case.application_keywords[:3])
  return QueryPlan(
    intent_id=f"theme_validation_{case.theme_id}",
    purpose="User theme validation patent candidate search",
    query_hint=case.theme_name,
    must_have_terms=must_have,
    should_have_terms=should_have,
    exclude_terms=list(case.exclude_keywords),
    target_countries=["US"],
    max_results=max_results,
    notes=["Generated by theme validation UI; keywords may be sent to BigQuery."],
  )


def run_theme_patent_search(
  case: ThemeValidationCase,
  *,
  project_root: Path | str,
  max_patents: int = 5,
  execute: bool = True,
) -> ThemeValidationRunResult:
  """Run patent candidate search only when BigQuery is configured and execute=True."""
  from tech_cartography.retrieval.bigquery_env import check_bigquery_environment, resolve_project_id
  from tech_cartography.retrieval.bigquery_light_retriever import RetrievalConfig, run_query_plan

  root = Path(project_root)
  queries = build_theme_search_queries(case)
  env = check_bigquery_environment()
  project = resolve_project_id()
  warnings = list(THEME_VALIDATION_SAFETY_MESSAGES[1:3])

  base_stages = evaluate_existing_output_stages(project_root=root, case=case, search_queries=queries)
  stage_by_name = {stage.stage: stage for stage in base_stages}

  if not project.get("project_id") or env.get("overall_status") != "ok":
    stage_by_name["patent_candidates_available"] = _ui_stage(
      "patent_candidates_available",
      status="external_search_not_configured",
      reason="BigQuery プロジェクトまたは認証が未設定のため、外部検索を実行できません。",
      next_action="GOOGLE_CLOUD_PROJECT を設定するか、既存 outputs 検証のみ利用してください。",
    )
    warnings.append("external_search_not_configured: 検索計画のみ保存しました。")
    ordered = [stage_by_name.get(name, _ui_stage(name, status="not_run", reason="未評価", next_action="")) for name in UI_STAGE_NAMES]
    return ThemeValidationRunResult(
      theme_id=case.theme_id,
      created_at=_utc_now_iso(),
      mode="external_search",
      case=case,
      stages=ordered,
      search_queries=queries,
      warnings=warnings,
    )

  if not execute:
    stage_by_name["patent_candidates_available"] = _ui_stage(
      "patent_candidates_available",
      status="external_api_required",
      reason="外部検索の同意が必要です。",
      next_action="同意チェックを ON にして再実行してください。",
    )
    ordered = [stage_by_name.get(name) for name in UI_STAGE_NAMES]
    return ThemeValidationRunResult(
      theme_id=case.theme_id,
      created_at=_utc_now_iso(),
      mode="external_search",
      case=case,
      stages=[stage for stage in ordered if stage is not None],
      search_queries=queries,
      warnings=warnings,
    )

  plan = _build_query_plan_from_case(case, max_results=max_patents)
  config = RetrievalConfig(
    project_id=project.get("project_id"),
    dry_run=False,
    execute=True,
    max_results_per_intent=max_patents,
    output_dir=str(root / "outputs" / "validation" / "theme_validation" / case.theme_id / "patent_search"),
  )
  try:
    retrieval = run_query_plan(plan, config, limit=max_patents)
  except Exception as exc:  # noqa: BLE001
    stage_by_name["patent_candidates_available"] = _ui_stage(
      "patent_candidates_available",
      status="failed",
      reason=f"外部検索でエラーが発生しました: {exc}",
      next_action="認証・課金設定を確認するか、既存 outputs 検証を利用してください。",
    )
    ordered = [stage_by_name.get(name) for name in UI_STAGE_NAMES]
    return ThemeValidationRunResult(
      theme_id=case.theme_id,
      created_at=_utc_now_iso(),
      mode="external_search",
      case=case,
      stages=[stage for stage in ordered if stage is not None],
      search_queries=queries,
      warnings=warnings + [str(exc)],
    )

  records = list(retrieval.get("records") or [])
  stage_by_name["patent_candidates_available"] = _ui_stage(
    "patent_candidates_available",
    status="pass" if records else "output_missing",
    reason=(
      f"BigQuery から {len(records)} 件の候補を取得しました。"
      if records
      else "外部検索は完了しましたが候補が 0 件でした。"
    ),
    next_action="候補を確認し seed publication を選定してください。",
    output_path=str(config.output_dir),
  )
  ordered = [stage_by_name.get(name) for name in UI_STAGE_NAMES]
  return ThemeValidationRunResult(
    theme_id=case.theme_id,
    created_at=_utc_now_iso(),
    mode="external_search",
    case=case,
    stages=[stage for stage in ordered if stage is not None],
    search_queries=queries,
    patent_candidates=records[:max_patents],
    warnings=warnings,
    output_paths={"patent_search_dir": str(config.output_dir)},
  )


def create_manual_claims_template(
  publication_number: str,
  output_dir: Path | str,
  *,
  project_root: Path | str | None = None,
) -> Path:
  pub = str(publication_number).strip()
  if not pub:
    raise ValueError("publication_number is required")

  payload = {
    "publication_number": pub,
    "title": "",
    "claims_text": "",
    "description_excerpt": "",
    "source": "manual_input",
    "notes": (
      "Independent claims を claims_text に貼り付け、"
      f"outputs/manual_fulltext_inputs/{pub}.json として保存すると次段階に進めます。"
    ),
  }
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  path = out / f"manual_claims_template_{pub}.json"
  path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

  root = Path(project_root) if project_root else out
  for _ in range(4):
    if (root / "outputs").exists():
      break
    if root.parent == root:
      root = out
      break
    root = root.parent
  manual_dir = root / "outputs" / "manual_fulltext_inputs"
  manual_dir.mkdir(parents=True, exist_ok=True)
  template_path = manual_dir / f"{pub}.template.json"
  template_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
  return path


def render_theme_validation_markdown(result: ThemeValidationRunResult) -> str:
  lines = [
    f"# Theme Validation Report: {result.theme_id}",
    "",
    f"- theme_name: {result.case.theme_name}",
    f"- mode: {result.mode}",
    f"- created_at: {result.created_at}",
    "",
    "## Safety",
    "",
  ]
  for message in THEME_VALIDATION_SAFETY_MESSAGES:
    lines.append(f"- {message}")

  if result.search_queries:
    lines.extend(["", "## Search plan", ""])
    for query in result.search_queries:
      lines.append(f"- `{query}`")

  lines.extend(["", "## Stage matrix", "", "| stage | status | reason | next_action | output_path |", "|---|---|---|---|---|"])
  for stage in result.stages:
    lines.append(
      f"| {stage.stage} | {stage.status} | {stage.reason} | {stage.next_action} | {stage.output_path} |",
    )

  if result.warnings:
    lines.extend(["", "## Warnings", ""])
    for warning in result.warnings:
      lines.append(f"- {warning}")

  lines.extend(
    [
      "",
      "## 注意",
      "",
      f"- {VALIDATION_CAUTION}",
      "- 本レポートは FTO・侵害・有効性の判断を行いません。",
      "",
    ],
  )
  return "\n".join(lines)


def save_theme_validation_result(
  result: ThemeValidationRunResult,
  output_dir: Path | str,
) -> dict[str, Path]:
  out = Path(output_dir) / result.theme_id
  out.mkdir(parents=True, exist_ok=True)
  paths: dict[str, Path] = {
    "theme_validation_report_md": out / "theme_validation_report.md",
    "theme_validation_result_json": out / "theme_validation_result.json",
    "theme_validation_matrix_csv": out / "theme_validation_matrix.csv",
    "search_plan_json": out / "search_plan.json",
  }

  paths["theme_validation_report_md"].write_text(
    render_theme_validation_markdown(result),
    encoding="utf-8",
  )
  paths["theme_validation_result_json"].write_text(
    json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
    encoding="utf-8",
  )

  search_plan = {
    "theme_id": result.theme_id,
    "theme_name": result.case.theme_name,
    "keywords": result.case.to_dict(),
    "search_queries": result.search_queries,
    "mode": result.mode,
    "created_at": result.created_at,
  }
  paths["search_plan_json"].write_text(
    json.dumps(search_plan, indent=2, ensure_ascii=False),
    encoding="utf-8",
  )

  with paths["theme_validation_matrix_csv"].open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(
      handle,
      fieldnames=["stage", "status", "reason", "next_action", "output_path"],
    )
    writer.writeheader()
    for stage in result.stages:
      writer.writerow(stage.to_dict())

  result.output_paths = {key: str(path) for key, path in paths.items()}
  return paths


def stage_status_display_class(status: str) -> str:
  if status == "pass":
    return "success"
  if status in {"manual_input_required", "external_api_required", "external_search_not_configured"}:
    return "caution"
  if status in {"blocked", "failed"}:
    return "warning"
  return "info"
