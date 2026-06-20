"""Cross-theme validation smoke — read existing outputs only by default (Phase 24.4)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
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


@dataclass
class ThemeValidationCase:
  theme_id: str
  theme_name: str
  description: str
  core_keywords: list[str]
  application_keywords: list[str]
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
      exclude_keywords=[str(v) for v in data.get("exclude_keywords", []) if str(v).strip()],
      seed_publication_numbers=[
        str(v).strip() for v in data.get("seed_publication_numbers", []) if str(v).strip()
      ],
      validation_goal=str(data.get("validation_goal", "")).strip(),
    )


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
