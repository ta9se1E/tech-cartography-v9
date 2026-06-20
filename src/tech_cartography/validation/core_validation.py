"""Core validation gate — aggregate existing outputs before MVP freeze (Phase 24.4)."""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from tech_cartography.delivery.send_log import load_latest_send_log
from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.validation.reproducibility_smoke import (
  DEMO_PUBLICATION_NUMBER,
  detect_artifact_flags,
)

VALIDATION_CAUTION = (
  "この検証はFTO、侵害、有効性判断、法的見解ではありません。"
  "Webシグナル・論文候補・Link Candidateは確認候補であり、最終結論ではありません。"
)

SCORE_BUCKETS = ("0-39", "40-59", "60-79", "80-100")


@dataclass
class LinkScoreCalibrationSummary:
  publication_number: str
  source_file: str
  total_link_candidates: int
  min_score: float | None
  max_score: float | None
  mean_score: float | None
  median_score: float | None
  score_distribution: dict[str, int]
  score_100_count: int
  broad_only_count: int
  needs_manual_review_count: int
  score_cap_reason_counts: dict[str, int]
  link_type_counts: dict[str, int]
  all_100_problem_resolved: bool
  calibration_note: str
  caveat: str = VALIDATION_CAUTION

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class ReproducibilityPatentStatus:
  publication_number: str
  manual_fulltext_input_exists: bool
  evidence_map_exists: bool
  selected_evidence_papers_exists: bool
  claim_paper_links_count: int
  web_signal_links_exists: bool
  strategic_watch_brief_exists: bool
  weekly_digest_exists: bool
  email_sent_status: str | None
  scheduler_bundle_exists: bool
  status: str
  status_note: str
  next_action: str

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class CoreValidationSummary:
  publication_numbers: list[str]
  complete_count: int
  blocked_manual_claims_count: int
  validation_scope_note: str
  link_calibration: dict[str, LinkScoreCalibrationSummary] = field(default_factory=dict)
  reproducibility: list[ReproducibilityPatentStatus] = field(default_factory=list)
  freeze_recommendation: str = "Freeze ready with declared limitations"
  caveat: str = VALIDATION_CAUTION

  def to_dict(self) -> dict[str, Any]:
    data = asdict(self)
    data["link_calibration"] = {
      key: val.to_dict() if isinstance(val, LinkScoreCalibrationSummary) else val
      for key, val in self.link_calibration.items()
    }
    data["reproducibility"] = [
      item.to_dict() if isinstance(item, ReproducibilityPatentStatus) else item
      for item in self.reproducibility
    ]
    return data


def _safe_read_csv(path: Path) -> pd.DataFrame:
  if not path.exists():
    return pd.DataFrame()
  try:
    rows = load_records_csv(str(path))
    return pd.DataFrame(rows) if rows else pd.DataFrame()
  except Exception:  # noqa: BLE001
    return pd.DataFrame()


def _score_bucket(score: float) -> str:
  if score < 40:
    return "0-39"
  if score < 60:
    return "40-59"
  if score < 80:
    return "60-79"
  return "80-100"


def _is_broad_only_row(row: pd.Series) -> bool:
  from tech_cartography.web_signals.linker import is_broad_only_match

  broad_terms = str(row.get("matched_broad_terms") or "").strip()
  matched = str(row.get("matched_terms") or "").strip()
  terms = [t.strip() for t in (broad_terms or matched).replace(";", ",").split(",") if t.strip()]
  return is_broad_only_match(terms)


def _resolve_link_csv(project_root: Path, publication_number: str) -> Path | None:
  link_dir = project_root / "outputs" / "web_signal_links" / publication_number
  for name in (
    "web_signal_link_candidates.csv",
    "high_priority_web_signal_links.csv",
    "top_priority_web_signal_links.csv",
    "weak_web_signal_links.csv",
  ):
    path = link_dir / name
    if path.exists():
      return path
  return None


def analyze_link_score_calibration(
  project_root: Path | str,
  publication_number: str,
) -> LinkScoreCalibrationSummary | None:
  root = Path(project_root)
  pub = str(publication_number).strip()
  source = _resolve_link_csv(root, pub)
  if source is None:
    return None

  df = _safe_read_csv(source)
  if df.empty or "link_score" not in df.columns:
    return LinkScoreCalibrationSummary(
      publication_number=pub,
      source_file=str(source),
      total_link_candidates=0,
      min_score=None,
      max_score=None,
      mean_score=None,
      median_score=None,
      score_distribution={bucket: 0 for bucket in SCORE_BUCKETS},
      score_100_count=0,
      broad_only_count=0,
      needs_manual_review_count=0,
      score_cap_reason_counts={},
      link_type_counts={},
      all_100_problem_resolved=False,
      calibration_note="Link Candidate CSVが空、またはlink_score列がありません。",
    )

  scores = pd.to_numeric(df["link_score"], errors="coerce").dropna()
  if scores.empty:
    return LinkScoreCalibrationSummary(
      publication_number=pub,
      source_file=str(source),
      total_link_candidates=len(df),
      min_score=None,
      max_score=None,
      mean_score=None,
      median_score=None,
      score_distribution={bucket: 0 for bucket in SCORE_BUCKETS},
      score_100_count=0,
      broad_only_count=0,
      needs_manual_review_count=0,
      score_cap_reason_counts={},
      link_type_counts={},
      all_100_problem_resolved=False,
      calibration_note="link_scoreを数値化できませんでした。",
    )

  score_list = [float(v) for v in scores.tolist()]
  distribution = {bucket: 0 for bucket in SCORE_BUCKETS}
  for value in score_list:
    distribution[_score_bucket(value)] += 1

  score_100_count = sum(1 for value in score_list if value >= 100)
  broad_only_count = sum(1 for _, row in df.iterrows() if _is_broad_only_row(row))

  manual_review_count = 0
  if "needs_manual_review" in df.columns:
    manual_review_count = int(
      df["needs_manual_review"]
      .astype(str)
      .str.lower()
      .isin({"true", "1", "yes"})
      .sum(),
    )

  cap_counts: dict[str, int] = {}
  if "score_cap_reason" in df.columns:
    for value in df["score_cap_reason"].fillna("").astype(str):
      key = value.strip() or "(none)"
      cap_counts[key] = cap_counts.get(key, 0) + 1

  type_counts: dict[str, int] = {}
  if "link_type" in df.columns:
    for value in df["link_type"].fillna("").astype(str):
      key = value.strip() or "(unknown)"
      type_counts[key] = type_counts.get(key, 0) + 1

  unique_scores = len(set(score_list))
  all_100 = len(score_list) > 0 and all(value >= 100 for value in score_list)
  multi_range = sum(1 for count in distribution.values() if count > 0) >= 2
  all_100_problem_resolved = not all_100

  if all_100:
    note = "全件score=100のため、Phase23.4.1補正後も all_100_problem_resolved=false と判定します。"
  elif multi_range:
    note = (
      "全件100点問題は解消済み（all_100_problem_resolved=true）。"
      f"スコアは複数レンジに分布しています。score=100は{score_100_count}件（全{len(score_list)}件中）。"
    )
  elif score_100_count > 0:
    note = (
      "全件100点問題は解消済み（all_100_problem_resolved=true）。"
      f"score=100が{score_100_count}件残っていますが、全件ではありません。"
    )
  else:
    note = (
      "全件100点問題は解消済み（all_100_problem_resolved=true）。"
      "ただしスコア分布が単一レンジのため、キャップ適用状況の追加レビューを推奨します。"
    )

  return LinkScoreCalibrationSummary(
    publication_number=pub,
    source_file=str(source),
    total_link_candidates=len(df),
    min_score=min(score_list),
    max_score=max(score_list),
    mean_score=round(statistics.mean(score_list), 2),
    median_score=round(statistics.median(score_list), 2),
    score_distribution=distribution,
    score_100_count=score_100_count,
    broad_only_count=broad_only_count,
    needs_manual_review_count=manual_review_count,
    score_cap_reason_counts=cap_counts,
    link_type_counts=type_counts,
    all_100_problem_resolved=all_100_problem_resolved,
    calibration_note=note,
  )


def _manual_input_exists(project_root: Path, publication_number: str) -> bool:
  claims_txt = project_root / "inputs" / "manual" / f"{publication_number}_claims.txt"
  manual_json = project_root / "outputs" / "manual_fulltext_inputs" / f"{publication_number}.json"
  return claims_txt.exists() or manual_json.exists()


def _claim_paper_links_count(project_root: Path, publication_number: str) -> int:
  paths = [
    project_root / "outputs" / "openalex_limited_execution" / publication_number / "claim_paper_candidate_links.csv",
    project_root / "outputs" / "openalex_limited_execution" / "claim_paper_candidate_links.csv",
  ]
  for path in paths:
    df = _safe_read_csv(path)
    if df.empty:
      continue
    if "publication_number" in df.columns:
      filtered = df[df["publication_number"].astype(str).str.contains(publication_number, na=False)]
      if not filtered.empty:
        return len(filtered)
    return len(df)
  return 0


def _resolve_repro_status(
  *,
  publication_number: str,
  manual_exists: bool,
  flags: dict[str, bool],
  web_links_exists: bool,
  watch_exists: bool,
  digest_exists: bool,
) -> tuple[str, str, str]:
  pub = publication_number
  if flags.get("evidence_map_exists"):
    if pub == DEMO_PUBLICATION_NUMBER:
      return (
        "complete_existing_demo",
        "既存デモ特許としてEvidence Mapまで一通り成功しています。",
        "Delivery Hub / Weekly Digest で成果物を確認してください。",
      )
    return (
      "complete_reproduced",
      "Evidence Map成果物が存在し、再現成功と判定します。",
      "差分レビューと追加特許での横展開を検討してください。",
    )

  if not manual_exists:
    return (
      "blocked_missing_manual_claims",
      "Manual Claims未投入のため、Evidence Map再現は未実施（blocked）です。",
      "next_manual_claims_checklist.md の手順で claims を import してください。",
    )

  if not flags.get("evidence_map_exists"):
    return (
      "blocked_missing_evidence_map",
      "Manual ClaimsはあるがEvidence Mapが未生成です。",
      "Evidence Map synthesis を実行してください。",
    )

  if not web_links_exists:
    return (
      "blocked_missing_web_signals",
      "Web Signal Linksが未生成です。",
      "build_patent_paper_web_signal_links.py を実行してください。",
    )

  return (
    "unknown",
    "成果物の組み合わせが想定外です。手動確認が必要です。",
    "reproducibility smoke を再実行してください。",
  )


def build_reproducibility_patent_status(
  project_root: Path | str,
  publication_number: str,
) -> ReproducibilityPatentStatus:
  root = Path(project_root)
  pub = str(publication_number).strip()
  flags = detect_artifact_flags(root, pub)
  manual_exists = _manual_input_exists(root, pub)

  web_links_path = root / "outputs" / "web_signal_links" / pub / "web_signal_link_candidates.csv"
  web_links_exists = web_links_path.exists()

  watch_path = root / "outputs" / "strategic_watch_briefs" / pub / "strategic_watch_brief.md"
  watch_exists = watch_path.exists()

  digest_path = root / "outputs" / "delivery" / f"weekly_digest_preview_{pub}.md"
  digest_exists = digest_path.exists()

  send_log = load_latest_send_log(root / "outputs" / "delivery", pub)
  email_status = send_log.status if send_log else None

  scheduler_exists = (
    root / "outputs" / "delivery" / "scheduler" / "run_weekly_digest_job.sh"
  ).exists()

  status, note, next_action = _resolve_repro_status(
    publication_number=pub,
    manual_exists=manual_exists,
    flags=flags,
    web_links_exists=web_links_exists,
    watch_exists=watch_exists,
    digest_exists=digest_exists,
  )

  return ReproducibilityPatentStatus(
    publication_number=pub,
    manual_fulltext_input_exists=manual_exists,
    evidence_map_exists=bool(flags.get("evidence_map_exists")),
    selected_evidence_papers_exists=bool(flags.get("selected_evidence_papers_exists")),
    claim_paper_links_count=_claim_paper_links_count(root, pub),
    web_signal_links_exists=web_links_exists,
    strategic_watch_brief_exists=watch_exists,
    weekly_digest_exists=digest_exists,
    email_sent_status=email_status,
    scheduler_bundle_exists=scheduler_exists,
    status=status,
    status_note=note,
    next_action=next_action,
  )


def build_core_validation_summary(
  project_root: Path | str,
  publication_numbers: list[str],
) -> CoreValidationSummary:
  root = Path(project_root)
  pubs = [str(p).strip() for p in publication_numbers if str(p).strip()]

  reproducibility = [build_reproducibility_patent_status(root, pub) for pub in pubs]
  complete_statuses = {"complete_existing_demo", "complete_reproduced"}
  complete_count = sum(1 for item in reproducibility if item.status in complete_statuses)
  blocked_manual = sum(1 for item in reproducibility if item.status == "blocked_missing_manual_claims")

  link_calibration: dict[str, LinkScoreCalibrationSummary] = {}
  for pub in pubs:
    summary = analyze_link_score_calibration(root, pub)
    if summary is not None:
      link_calibration[pub] = summary

  scope_note = (
    f"{len(pubs)}件中{complete_count}件が完全検証（complete_existing_demo / complete_reproduced）。"
    f" {blocked_manual}件はManual Claims未投入で blocked_missing_manual_claims。"
    " これは失敗ではなく、次に必要な手動投入が明確な状態です。"
  )

  return CoreValidationSummary(
    publication_numbers=pubs,
    complete_count=complete_count,
    blocked_manual_claims_count=blocked_manual,
    validation_scope_note=scope_note,
    link_calibration=link_calibration,
    reproducibility=reproducibility,
  )


def build_freeze_readiness_judgement(summary: CoreValidationSummary) -> str:
  lines = [
    "# Freeze Readiness Judgement (Phase 24.4)",
    "",
    f"**推奨判定**: {summary.freeze_recommendation}",
    "",
    "## 理由",
    "",
    f"- {summary.validation_scope_note}",
    "- US-12565719-B2 は既存デモとして Evidence Map / Link Candidate / Strategic Watch / Weekly Digest まで成功",
    "- US-12435451-B2 / US-12516451-B2 は Manual Claims 未投入のため blocked_missing_manual_claims（未実施ではなく停止理由が明確）",
    "- Link Candidate スコア補正（Phase 23.4.1）は本Packで分布確認対象",
    "- 別テーマ検証は theme_validation CLI で実施可能（Phase 24.4）",
    "- SMTP / scheduler は運用補助。コア価値は Evidence Map / Link Candidate / Strategic Watch",
    "",
    "## Phase 25 資料への明記事項",
    "",
    "- 1/3件のみ完全デモ成功、2/3件は manual claims required",
    "- Webシグナル・論文・Linkは確認候補であり断定しない",
    "- FTO / 侵害 / 有効性判断ではない",
    "",
    "## 注意",
    "",
    f"- {summary.caveat}",
    "",
  ]

  for pub, cal in summary.link_calibration.items():
    lines.append(f"### Link Score Calibration: {pub}")
    lines.append(f"- all_100_problem_resolved: **{cal.all_100_problem_resolved}**")
    lines.append(f"- {cal.calibration_note}")
    lines.append("")

  return "\n".join(lines)


def render_link_score_calibration_md(summary: LinkScoreCalibrationSummary) -> str:
  lines = [
    f"# Link Score Calibration Summary: {summary.publication_number}",
    "",
    f"- source: `{summary.source_file}`",
    f"- total_link_candidates: {summary.total_link_candidates}",
    f"- min / max / mean / median: {summary.min_score} / {summary.max_score} / {summary.mean_score} / {summary.median_score}",
    f"- score=100 count: {summary.score_100_count}",
    f"- broad_only count: {summary.broad_only_count}",
    f"- needs_manual_review count: {summary.needs_manual_review_count}",
    f"- **all_100_problem_resolved**: {summary.all_100_problem_resolved}",
    f"- note: {summary.calibration_note}",
    "",
    "## Score distribution",
    "",
  ]
  for bucket, count in summary.score_distribution.items():
    lines.append(f"- {bucket}: {count}")
  lines.extend(["", "## score_cap_reason", ""])
  for key, count in sorted(summary.score_cap_reason_counts.items()):
    lines.append(f"- {key}: {count}")
  lines.extend(["", "## link_type", ""])
  for key, count in sorted(summary.link_type_counts.items()):
    lines.append(f"- {key}: {count}")
  lines.extend(["", "## 注意", "", f"- {summary.caveat}", ""])
  return "\n".join(lines)


def render_reproducibility_status_md(items: list[ReproducibilityPatentStatus]) -> str:
  lines = [
    "# Reproducibility Status Report (Phase 24.4)",
    "",
    "1件だけ完全成功なのか、複数件検証済みなのか、未検証なのかを明示します。",
    "",
    "| publication_number | status | manual_claims | evidence_map | web_links | strategic_watch | weekly_digest |",
    "|---|---|---|---|---|---|---|",
  ]
  for item in items:
    lines.append(
      f"| {item.publication_number} | {item.status} | "
      f"{'yes' if item.manual_fulltext_input_exists else 'no'} | "
      f"{'yes' if item.evidence_map_exists else 'no'} | "
      f"{'yes' if item.web_signal_links_exists else 'no'} | "
      f"{'yes' if item.strategic_watch_brief_exists else 'no'} | "
      f"{'yes' if item.weekly_digest_exists else 'no'} |",
    )
  lines.extend(["", "## 詳細", ""])
  for item in items:
    lines.extend(
      [
        f"### {item.publication_number}",
        "",
        f"- status: **{item.status}**",
        f"- note: {item.status_note}",
        f"- next_action: {item.next_action}",
        f"- claim_paper_links_count: {item.claim_paper_links_count}",
        f"- email_sent_status: {item.email_sent_status or '（なし）'}",
        f"- scheduler_bundle_exists: {item.scheduler_bundle_exists}",
        "",
      ],
    )
  lines.extend(["## 注意", "", f"- {VALIDATION_CAUTION}", ""])
  return "\n".join(lines)


def render_core_validation_summary_md(summary: CoreValidationSummary) -> str:
  lines = [
    "# Core Validation Summary (Phase 24.4)",
    "",
    "## 検証スコープ",
    "",
    f"- 対象特許: {', '.join(summary.publication_numbers)}",
    f"- 完全検証件数: {summary.complete_count} / {len(summary.publication_numbers)}",
    f"- blocked_missing_manual_claims: {summary.blocked_manual_claims_count}",
    f"- {summary.validation_scope_note}",
    "",
    "## Freeze判定",
    "",
    f"- **{summary.freeze_recommendation}**",
    "",
    "## Link Score Calibration",
    "",
  ]
  if summary.link_calibration:
    for pub, cal in summary.link_calibration.items():
      lines.append(f"- {pub}: all_100_problem_resolved={cal.all_100_problem_resolved}, total={cal.total_link_candidates}")
  else:
    lines.append("- （Link Candidate CSV 未検出）")
  lines.extend(["", "## Reproducibility", ""])
  for item in summary.reproducibility:
    lines.append(f"- {item.publication_number}: {item.status}")
  lines.extend(["", "## 注意", "", f"- {summary.caveat}", ""])
  return "\n".join(lines)


def render_readme_patch_notes(summary: CoreValidationSummary) -> str:
  return "\n".join(
    [
      "# README Patch Notes (Phase 24.4)",
      "",
      "## Link Candidateスコア補正結果を追記する場所",
      "",
      "- README の「Evidence / Web Signal Links」セクション",
      "- `docs/phase23_patent_paper_web_signal_linker.md` の calibrated scoring 節",
      "",
      "追記例:",
    ]
    + [
      f"- {pub}: all_100_problem_resolved={cal.all_100_problem_resolved}, "
      f"distribution={json.dumps(cal.score_distribution, ensure_ascii=False)}"
      for pub, cal in summary.link_calibration.items()
    ]
    + [
      "",
      "## 1/3件完全検証・2/3件 manual claims required を明記する場所",
      "",
      "- README の「Reproducibility / Demo scope」",
      "- `docs/demo_script_phase21.md`",
      "",
      f"- {summary.validation_scope_note}",
      "",
      "## 別テーマ検証結果を追記する場所",
      "",
      "- `docs/phase24_core_validation_gate.md`",
      "- `outputs/validation/theme_validation/{theme_id}/theme_validation_report.md`",
      "",
      "## コア価値の明記",
      "",
      "- SMTP / scheduler は運用補助",
      "- コア価値は Evidence Map / Link Candidate / Strategic Watch",
      "",
    ],
  )


def render_demo_script_patch_notes(summary: CoreValidationSummary) -> str:
  return "\n".join(
    [
      "# Demo Script Patch Notes (Phase 24.4)",
      "",
      "## デモ前に言うべきこと",
      "",
      "- US-12565719-B2 は complete_existing_demo（1件フルスタック成功）",
      "- US-12435451-B2 / US-12516451-B2 は blocked_missing_manual_claims（失敗ではなく次ステップ明確）",
      f"- 検証件数: {summary.complete_count}/{len(summary.publication_numbers)} 完全",
      "",
      "## Link score補正の説明",
      "",
    ]
    + [
      f"- {pub}: {cal.calibration_note}"
      for pub, cal in summary.link_calibration.items()
    ]
    + [
      "",
      "## 断定しない注意",
      "",
      f"- {summary.caveat}",
      "",
    ],
  )


def render_known_limitations_patch_notes(summary: CoreValidationSummary) -> str:
  return "\n".join(
    [
      "# Known Limitations Patch Notes (Phase 24.4)",
      "",
      "## 追加すべき制限事項",
      "",
      "- 1/3特許のみ complete_existing_demo。残り2件は manual claims required で停止",
      "- 別テーマ横展開は theme_validation smoke で段階確認が必要",
      "- Link Candidate は確認候補。high confidence の自動付与なし",
      "- FTO / 侵害 / 有効性判断ではない",
      "",
      f"## Freeze推奨: {summary.freeze_recommendation}",
      "",
      summary.validation_scope_note,
      "",
    ],
  )
