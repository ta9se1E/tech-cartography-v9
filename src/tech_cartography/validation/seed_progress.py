"""Seed-level validation progress inspection (Phase 24.4A.4)."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from tech_cartography.validation.manual_claims_evidence_builder import evidence_map_output_dir
from tech_cartography.validation.theme_validation import (
  has_manual_claims,
  manual_claims_json_path,
  manual_claims_template_path,
)

MANUAL_CLAIMS_LABEL_JA = {
  "saved": "保存済み",
  "template_only": "テンプレートのみ",
  "empty": "claims_text空",
  "missing": "未投入",
}
EVIDENCE_MAP_LABEL_JA = {
  "full_map_exists": "本格Evidence Map",
  "skeleton_exists": "skeletonあり",
  "missing": "未生成",
}
STAGE_LABEL_JA = {
  "pass": "pass",
  "manual_input_required": "要Manual Claims",
  "output_missing": "未完了",
}


@dataclass
class SeedValidationProgress:
  publication_number: str
  manual_claims_status: str
  evidence_map_status: str
  claim_elements_status: str
  query_plan_status: str
  stage2_status: str
  stage3_status: str
  next_action: str
  manual_claims_path: str
  evidence_map_skeleton_path: str
  claim_elements_path: str
  query_plan_path: str

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


def _evidence_map_status(root: Path, publication_number: str) -> str:
  out = evidence_map_output_dir(root, publication_number)
  if (out / "evidence_map_synthesis.json").exists():
    return "full_map_exists"
  if (out / "evidence_map_skeleton.json").exists():
    return "skeleton_exists"
  return "missing"


def _artifact_exists(path: Path) -> str:
  return "exists" if path.exists() else "missing"


def _compute_stage2(manual_claims_status: str) -> str:
  return "pass" if manual_claims_status == "saved" else "manual_input_required"


def _compute_stage3(evidence_map_status: str) -> str:
  return "pass" if evidence_map_status in {"full_map_exists", "skeleton_exists"} else "output_missing"


def _compute_next_action(
  *,
  manual_claims_status: str,
  evidence_map_status: str,
  publication_number: str,
) -> str:
  if manual_claims_status == "missing":
    return "Manual Claimsを貼り付けて保存してください"
  if manual_claims_status == "template_only":
    return "Manual Claimsテンプレートにclaims_textを貼り付けて保存してください"
  if manual_claims_status == "empty":
    return "claims_textが空です。Manual Claimsを貼り付けて保存してください"
  if evidence_map_status == "missing":
    return "Evidence Map skeletonを生成してください"
  if evidence_map_status == "skeleton_exists":
    return "Stage 3まで完了。次は論文候補/Webシグナル候補の取得計画へ進めます（外部APIは未実行）"
  if evidence_map_status == "full_map_exists":
    return "Full Evidence Mapあり"
  return f"{publication_number} の次アクションを確認してください"


def inspect_seed_progress(publication_number: str, output_root: Path | str) -> SeedValidationProgress:
  root = Path(output_root)
  pub = str(publication_number).strip()
  _ok, manual_status = has_manual_claims(pub, root)
  evidence_status = _evidence_map_status(root, pub)
  ev_dir = evidence_map_output_dir(root, pub)
  claim_elements_path = ev_dir / "claim_elements.csv"
  query_plan_path = ev_dir / "query_plan.json"
  skeleton_path = ev_dir / "evidence_map_skeleton.json"
  manual_path = manual_claims_json_path(root, pub)
  if not manual_path.exists() and manual_claims_template_path(root, pub).exists():
    manual_path = manual_claims_template_path(root, pub)

  return SeedValidationProgress(
    publication_number=pub,
    manual_claims_status=manual_status,
    evidence_map_status=evidence_status,
    claim_elements_status=_artifact_exists(claim_elements_path),
    query_plan_status=_artifact_exists(query_plan_path),
    stage2_status=_compute_stage2(manual_status),
    stage3_status=_compute_stage3(evidence_status),
    next_action=_compute_next_action(
      manual_claims_status=manual_status,
      evidence_map_status=evidence_status,
      publication_number=pub,
    ),
    manual_claims_path=str(manual_path) if manual_path.exists() else str(manual_claims_json_path(root, pub)),
    evidence_map_skeleton_path=str(skeleton_path),
    claim_elements_path=str(claim_elements_path),
    query_plan_path=str(query_plan_path),
  )


def inspect_seed_progress_many(
  publication_numbers: list[str],
  output_root: Path | str,
) -> list[SeedValidationProgress]:
  seen: set[str] = set()
  items: list[SeedValidationProgress] = []
  for raw in publication_numbers:
    pub = str(raw).strip()
    if not pub or pub in seen:
      continue
    seen.add(pub)
    items.append(inspect_seed_progress(pub, output_root))
  return items


def progress_to_dataframe(progress_list: list[SeedValidationProgress]) -> pd.DataFrame:
  rows = [item.to_dict() for item in progress_list]
  if not rows:
    return pd.DataFrame(
      columns=[
        "publication_number",
        "manual_claims_status",
        "evidence_map_status",
        "stage2_status",
        "stage3_status",
        "next_action",
      ],
    )
  return pd.DataFrame(rows)


def progress_to_display_dataframe(progress_list: list[SeedValidationProgress]) -> pd.DataFrame:
  rows: list[dict[str, str]] = []
  for item in progress_list:
    rows.append(
      {
        "publication_number": item.publication_number,
        "Manual Claims": MANUAL_CLAIMS_LABEL_JA.get(item.manual_claims_status, item.manual_claims_status),
        "Evidence Map": EVIDENCE_MAP_LABEL_JA.get(item.evidence_map_status, item.evidence_map_status),
        "Stage 2": STAGE_LABEL_JA.get(item.stage2_status, item.stage2_status),
        "Stage 3": STAGE_LABEL_JA.get(item.stage3_status, item.stage3_status),
        "next_action": item.next_action,
      },
    )
  return pd.DataFrame(rows)


def preferred_publication_for_manual_claims(
  progress_list: list[SeedValidationProgress],
) -> str:
  for status in ("missing", "template_only", "empty"):
    for item in progress_list:
      if item.manual_claims_status == status:
        return item.publication_number
  for item in progress_list:
    if item.manual_claims_status == "saved":
      return item.publication_number
  return progress_list[0].publication_number if progress_list else ""


def preferred_publication_for_evidence_map(
  progress_list: list[SeedValidationProgress],
) -> str:
  for item in progress_list:
    if item.manual_claims_status == "saved" and item.evidence_map_status == "missing":
      return item.publication_number
  return preferred_publication_for_manual_claims(progress_list)


def summarize_seed_progress_actions(
  progress_list: list[SeedValidationProgress],
) -> tuple[list[str], list[str]]:
  pending: list[str] = []
  completed: list[str] = []
  for item in progress_list:
    if item.stage2_status == "pass" and item.stage3_status == "pass":
      completed.append(f"{item.publication_number}: Stage 3まで完了")
      continue
    pending.append(f"{item.publication_number}: {item.next_action}")
  return pending, completed


def render_seed_progress_markdown(progress_list: list[SeedValidationProgress]) -> str:
  lines = [
    "# Seed Validation Progress",
    "",
    "Evidence Map skeletonは最終Evidence Mapではありません。論文・Web evidenceは未検証です。",
    "",
    "| publication_number | Manual Claims | Evidence Map | Stage 2 | Stage 3 | next_action |",
    "|---|---|---|---|---|---|",
  ]
  for item in progress_list:
    mc = MANUAL_CLAIMS_LABEL_JA.get(item.manual_claims_status, item.manual_claims_status)
    ev = EVIDENCE_MAP_LABEL_JA.get(item.evidence_map_status, item.evidence_map_status)
    lines.append(
      f"| {item.publication_number} | {mc} | {ev} | {item.stage2_status} | {item.stage3_status} | {item.next_action} |",
    )

  pending, completed = summarize_seed_progress_actions(progress_list)
  lines.extend(["", "## 次に進めるseed", ""])
  if pending:
    for row in pending:
      lines.append(f"- {row}")
  else:
    lines.append("- （なし）")

  lines.extend(["", "## 完了済みseed", ""])
  if completed:
    for row in completed:
      lines.append(f"- {row}")
  else:
    lines.append("- （なし）")

  lines.extend(
    [
      "",
      "## 注意",
      "",
      "- 外部API（OpenAlex / Tavily / BigQuery）はこのレポート生成では実行しません。",
      "- FTO、侵害、有効性判断は行いません。",
      "",
    ],
  )
  return "\n".join(lines)


def save_seed_progress_report(
  progress_list: list[SeedValidationProgress],
  output_dir: Path | str,
  theme_id: str,
) -> dict[str, Path]:
  out = Path(output_dir) / theme_id
  out.mkdir(parents=True, exist_ok=True)
  paths = {
    "seed_progress_report_md": out / "seed_progress_report.md",
    "seed_progress_report_csv": out / "seed_progress_report.csv",
    "seed_progress_report_json": out / "seed_progress_report.json",
  }
  paths["seed_progress_report_md"].write_text(
    render_seed_progress_markdown(progress_list),
    encoding="utf-8",
  )
  paths["seed_progress_report_json"].write_text(
    json.dumps([item.to_dict() for item in progress_list], indent=2, ensure_ascii=False),
    encoding="utf-8",
  )
  df = progress_to_dataframe(progress_list)
  if df.empty:
    paths["seed_progress_report_csv"].write_text("", encoding="utf-8")
  else:
    df.to_csv(paths["seed_progress_report_csv"], index=False, encoding="utf-8")
  return paths
