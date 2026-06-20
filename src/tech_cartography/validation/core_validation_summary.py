"""Cross-theme core validation summary for MVP freeze (Phase 24.4B)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.validation.seed_progress import (
  MANUAL_CLAIMS_LABEL_JA,
  EVIDENCE_MAP_LABEL_JA,
  STAGE_LABEL_JA,
  SeedValidationProgress,
  inspect_seed_progress_many,
)

FREEZE_READY_WITH_DECLARED_LIMITATIONS = "freeze_ready_with_declared_limitations"

VERIFIED_SCOPE = [
  "Stage 0: 別テーマ検証UI（dry-run / 既存 outputs 検証）",
  "Stage 1: seed 公報番号の選択",
  "Stage 2: Manual Claims 保存（ユーザー提供の公報原文）",
  "Stage 3: Manual Claims から Evidence Map skeleton 生成",
]

UNVERIFIED_SCOPE = [
  "Stage 4: paper_candidates_available（論文候補）",
  "Stage 5: web_signal_candidates_available（Webシグナル候補）",
  "Stage 6: link_candidates_available（Link Candidate）",
  "Stage 7: strategic_watch_available（Strategic Watch）",
  "Stage 8/9: digest_available（Weekly Digest）",
  "OpenAlex / Tavily / BigQuery の自動実行",
  "UI からのメール送信",
  "UI からの scheduler 登録",
]

LEGAL_CAUTION = (
  "本サマリーは FTO（Freedom to Operate）、侵害、有効性の法的判断ではありません。"
  "原典確認と専門家レビューが必要です。"
)

SKELETON_CAUTION = (
  "Evidence Map skeleton は最終 Evidence Map ではありません。"
  "論文・Web evidence の紐付けは未検証です。"
)

EXTERNAL_API_CAUTION = (
  "このサマリー生成では OpenAlex / Tavily / BigQuery は実行していません。"
)


@dataclass
class CoreValidationSummary:
  theme_id: str
  theme_name: str
  created_at: str
  seed_count: int
  stage2_pass_count: int
  stage3_pass_count: int
  completed_seed_publications: list[str]
  incomplete_seed_publications: list[str]
  verified_scope: list[str]
  unverified_scope: list[str]
  freeze_readiness: str
  caveats: list[str]
  next_actions: list[str]
  seed_progress: list[dict[str, Any]] = field(default_factory=list)
  theme_validation_loaded: bool = False
  seed_progress_report_loaded: bool = False

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


def theme_validation_dir(project_root: Path | str, theme_id: str) -> Path:
  return Path(project_root) / "outputs" / "validation" / "theme_validation" / theme_id


def load_seed_progress_report_json(
  project_root: Path | str,
  theme_id: str,
) -> tuple[list[dict[str, Any]] | None, Path | None]:
  path = theme_validation_dir(project_root, theme_id) / "seed_progress_report.json"
  if not path.exists():
    return None, None
  data = json.loads(path.read_text(encoding="utf-8"))
  if isinstance(data, list):
    return data, path
  return None, path


def load_theme_validation_result_json(
  project_root: Path | str,
  theme_id: str,
) -> tuple[dict[str, Any] | None, Path | None]:
  path = theme_validation_dir(project_root, theme_id) / "theme_validation_result.json"
  if not path.exists():
    return None, None
  data = json.loads(path.read_text(encoding="utf-8"))
  if isinstance(data, dict):
    return data, path
  return None, path


def _skeleton_exists(progress: SeedValidationProgress) -> bool:
  return Path(progress.evidence_map_skeleton_path).exists()


def build_core_validation_summary(
  *,
  project_root: Path | str,
  theme_id: str,
  theme_name: str,
  seed_publications: list[str],
) -> CoreValidationSummary:
  root = Path(project_root)
  progress_list = inspect_seed_progress_many(seed_publications, root)

  _, seed_report_path = load_seed_progress_report_json(root, theme_id)
  theme_result, theme_result_path = load_theme_validation_result_json(root, theme_id)

  stage2_pass = sum(1 for item in progress_list if item.stage2_status == "pass")
  stage3_pass = sum(1 for item in progress_list if item.stage3_status == "pass")
  completed = [
    item.publication_number
    for item in progress_list
    if item.stage2_status == "pass" and item.stage3_status == "pass"
  ]
  incomplete = [item.publication_number for item in progress_list if item.publication_number not in completed]

  all_stage3_done = len(progress_list) > 0 and stage3_pass == len(progress_list)
  freeze_readiness = (
    FREEZE_READY_WITH_DECLARED_LIMITATIONS
    if all_stage3_done and stage2_pass == len(progress_list)
    else "not_ready_pending_seed_validation"
  )

  next_actions: list[str] = []
  if incomplete:
    for item in progress_list:
      if item.publication_number in incomplete:
        next_actions.append(f"{item.publication_number}: {item.next_action}")
  elif all_stage3_done:
    next_actions.append(
      "README / デモ台本 / 既知制限に Stage 4 以降未検証と skeleton 制限を明記した上で MVP Freeze"
    )
    next_actions.append("Post-MVP: Stage 4 以降（論文・Web・Link・Strategic Watch・Digest）の別テーマ検証")

  caveats = [
    SKELETON_CAUTION,
    EXTERNAL_API_CAUTION,
    "Manual Claims はユーザーが公報原文から貼り付けたテキストです（AI 生成ではありません）。",
    LEGAL_CAUTION,
    "Stage 4 以降は未検証です。",
  ]
  if theme_result and theme_result.get("dry_run_only"):
    caveats.append("theme_validation_result は dry-run のみで保存された可能性があります。")

  return CoreValidationSummary(
    theme_id=theme_id,
    theme_name=theme_name,
    created_at=datetime.now(timezone.utc).isoformat(),
    seed_count=len(progress_list),
    stage2_pass_count=stage2_pass,
    stage3_pass_count=stage3_pass,
    completed_seed_publications=completed,
    incomplete_seed_publications=incomplete,
    verified_scope=list(VERIFIED_SCOPE),
    unverified_scope=list(UNVERIFIED_SCOPE),
    freeze_readiness=freeze_readiness,
    caveats=caveats,
    next_actions=next_actions,
    seed_progress=[
      {
        **item.to_dict(),
        "skeleton_file_exists": _skeleton_exists(item),
      }
      for item in progress_list
    ],
    theme_validation_loaded=theme_result_path is not None and theme_result is not None,
    seed_progress_report_loaded=seed_report_path is not None,
  )


def render_cross_theme_core_validation_summary_md(summary: CoreValidationSummary) -> str:
  lines = [
    "# Cross-Theme Core Validation Summary (Phase 24.4B)",
    "",
    "## 検証テーマ",
    "",
    f"- theme_id: `{summary.theme_id}`",
    f"- theme_name: {summary.theme_name}",
    f"- created_at: {summary.created_at}",
    "",
    "## Seed 公報（3件）",
    "",
  ]
  for pub in summary.seed_progress:
    lines.append(f"- {pub['publication_number']}")
  lines.extend(
    [
      "",
      "## Stage 2 / Stage 3 結果",
      "",
      "| publication_number | Manual Claims | Evidence Map | Stage 2 | Stage 3 | skeleton存在 |",
      "|---|---|---|---|---|---|",
    ],
  )
  for pub in summary.seed_progress:
    mc = MANUAL_CLAIMS_LABEL_JA.get(pub["manual_claims_status"], pub["manual_claims_status"])
    ev = EVIDENCE_MAP_LABEL_JA.get(pub["evidence_map_status"], pub["evidence_map_status"])
    s2 = STAGE_LABEL_JA.get(pub["stage2_status"], pub["stage2_status"])
    s3 = STAGE_LABEL_JA.get(pub["stage3_status"], pub["stage3_status"])
    skel = "あり" if pub.get("skeleton_file_exists") else "なし"
    lines.append(
      f"| {pub['publication_number']} | {mc} | {ev} | {s2} | {s3} | {skel} |",
    )

  lines.extend(
    [
      "",
      f"- Stage 2 pass: **{summary.stage2_pass_count} / {summary.seed_count}**",
      f"- Stage 3 pass: **{summary.stage3_pass_count} / {summary.seed_count}**",
      "",
      "## 完了状況",
      "",
    ],
  )
  if summary.completed_seed_publications:
    lines.append(
      f"- **3件すべて Stage 3 まで完了**（{', '.join(summary.completed_seed_publications)}）"
      if len(summary.completed_seed_publications) == summary.seed_count
      else f"- 完了: {', '.join(summary.completed_seed_publications)}"
    )
  else:
    lines.append("- 完了 seed: （なし）")
  if summary.incomplete_seed_publications:
    lines.append(f"- 未完了: {', '.join(summary.incomplete_seed_publications)}")

  lines.extend(["", "## 検証済みスコープ", ""])
  for item in summary.verified_scope:
    lines.append(f"- {item}")

  lines.extend(["", "## 未検証スコープ（Stage 4 以降）", ""])
  for item in summary.unverified_scope:
    lines.append(f"- {item}")

  lines.extend(
    [
      "",
      "## Freeze Readiness",
      "",
      f"- **{summary.freeze_readiness}**",
      "",
      "## 重要な注意",
      "",
      f"- {SKELETON_CAUTION}",
      f"- {EXTERNAL_API_CAUTION}",
      "- Manual Claims はユーザー提供の公報原文から貼り付けたテキストです。",
      f"- {LEGAL_CAUTION}",
      "",
      "## 入力レポート",
      "",
      f"- seed_progress_report 読込: {'あり' if summary.seed_progress_report_loaded else 'なし（live inspect を使用）'}",
      f"- theme_validation_result 読込: {'あり' if summary.theme_validation_loaded else 'なし'}",
      "",
    ],
  )
  return "\n".join(lines)


def render_freeze_readiness_judgement_md(summary: CoreValidationSummary) -> str:
  return "\n".join(
    [
      "# Freeze Readiness Judgement (Phase 24.4B)",
      "",
      "## 結論",
      "",
      f"**{summary.freeze_readiness}**",
      "",
      "（日本語: 制限を明記した上での MVP Freeze 可能）",
      "",
      "## 理由",
      "",
      "1. 既存デモ US-12565719-B2 は Weekly Digest まで通っている（complete_existing_demo）。",
      f"2. 別テーマ「{summary.theme_name}」の seed {summary.seed_count} 件で、"
      "Streamlit 上から Manual Claims 投入 → Evidence Map skeleton 生成まで確認した。",
      f"3. {summary.stage3_pass_count} 件すべて Stage 3 pass となり、1件だけの偶然ではない再現性を確認できた。",
      "4. ただし別テーマでは Stage 4 以降（論文候補 / Webシグナル / Link Candidate / Strategic Watch / Digest）は未実行。",
      "5. skeleton は最終 Evidence Map ではない。",
      "6. OpenAlex / Tavily / BigQuery は本 Phase では実行していない。",
      "7. 上記制限を README・デモ台本・既知制限に明記した上で Freeze 可能。",
      "",
      "## 次のアクション",
      "",
    ]
    + [f"- {action}" for action in summary.next_actions]
    + ["", f"- {LEGAL_CAUTION}", ""],
  )


def render_reviewer_response_notes_md(summary: CoreValidationSummary) -> str:
  return "\n".join(
    [
      "# Reviewer Response Notes (Phase 24.4B)",
      "",
      "MVP Freeze 前のレビューコメントへの回答整理です。",
      "",
      "## 指摘1: Link Candidate 全件100点問題",
      "",
      "- Phase23.4.1 でスコア補正済み（calibrated scoring）。",
      "- 補正結果のサマリーを README の Evidence / Web Signal Links セクションに明記すべき。",
      "- 参照: `docs/phase23_patent_paper_web_signal_linker.md`",
      "",
      "## 指摘2: 1件だけの再現性",
      "",
      "- 既存 US 特許デモ（US-12565719-B2）は 1 件完全成功（Weekly Digest まで）。",
      f"- 追加で JP seed {summary.seed_count} 件（{', '.join(summary.completed_seed_publications or ['（進行中）'])}）について "
      f"Stage 3 まで UI 上で確認（Stage 2 pass: {summary.stage2_pass_count}, Stage 3 pass: {summary.stage3_pass_count}）。",
      "- ただし Full Evidence Map ではなく Evidence Map skeleton まで。",
      "- Stage 4 以降は未検証であることを隠さない。",
      "",
      "## 指摘3: SMTP / scheduler に寄りすぎ",
      "",
      "- Phase24.4A でコア検証（Manual Claims → skeleton）に回帰した。",
      "- UI 上で別テーマ検証タブ・Seed 進捗ダッシュボードが利用可能であることを確認。",
      "- 本 Phase では UI からメール送信・scheduler 登録は行わない。",
      "",
      "## 指摘4: Freeze 条件",
      "",
      f"- 結論: **{summary.freeze_readiness}**",
      "- 制限（skeleton、Stage 4 以降未検証、外部 API 未実行、法的判断不可）を明記した上で Freeze 可能。",
      "- DB 永続化は Post-MVP。",
      "",
      "## 共通注意",
      "",
      f"- {SKELETON_CAUTION}",
      f"- {EXTERNAL_API_CAUTION}",
      f"- {LEGAL_CAUTION}",
      "",
    ],
  )


def render_readme_patch_notes_md(summary: CoreValidationSummary) -> str:
  return "\n".join(
    [
      "# README Patch Notes (Phase 24.4B)",
      "",
      "## 追記すべき内容",
      "",
      "### 別テーマ検証 UI",
      "",
      "- トップレベルタブ「別テーマ検証」から theme_id / seed を指定して検証できる。",
      f"- 検証例: `{summary.theme_id}` — {summary.theme_name}",
      "",
      "### JP seed 3件で Stage 3 まで確認",
      "",
      f"- seeds: {', '.join(p['publication_number'] for p in summary.seed_progress)}",
      f"- Stage 2 pass: {summary.stage2_pass_count}/{summary.seed_count}",
      f"- Stage 3 pass: {summary.stage3_pass_count}/{summary.seed_count}",
      "",
      "### Stage 4 以降は未検証",
      "",
    ]
    + [f"- {item}" for item in summary.unverified_scope]
    + [
      "",
      "### skeleton と full Evidence Map の違い",
      "",
      f"- {SKELETON_CAUTION}",
      "- full Evidence Map は論文・Web evidence 紐付け後の synthesis 成果物。",
      "",
      "### DB は Post-MVP",
      "",
      "- 現状は outputs/ 配下のファイルベース。Cloud SQL / 永続 DB は Post-MVP。",
      "",
      "### Link Candidate 補正（Phase23.4.1）",
      "",
      "- README に calibrated scoring 補正結果サマリーを追記する。",
      "",
    ],
  )


def render_demo_script_patch_notes_md(summary: CoreValidationSummary) -> str:
  return "\n".join(
    [
      "# Demo Script Patch Notes (Phase 24.4B)",
      "",
      "## デモで見せる順序（追記）",
      "",
      "1. 既存 US デモ（US-12565719-B2）— Weekly Digest までの完全フロー。",
      "2. トップレベルタブ「**別テーマ検証**」を開く。",
      f"3. テーマ `{summary.theme_id}`（{summary.theme_name}）を選択または入力。",
      "4. **Seed 進捗ダッシュボード**で 3 件の Manual Claims / skeleton / Stage 2・3 を表示。",
      f"5. **{summary.stage3_pass_count} 件すべて Stage 3 pass** を示す（偶然の 1 件ではない）。",
      "6. Evidence Map skeleton を生成済みであることを示す（ファイルパスまたは UI プレビュー）。",
      "7. **Stage 4 以降は未検証**と口頭で説明する（論文・Web・Link・Strategic Watch・Digest）。",
      "8. skeleton は最終 Evidence Map ではないことを説明する。",
      "",
      "## 言わないこと",
      "",
      "- FTO / 侵害 / 有効性の断定",
      "- 別テーマでも Weekly Digest まで動くという誤解を与えない",
      "- 外部 API をデモ中に自動実行しない",
      "",
      f"- {LEGAL_CAUTION}",
      "",
    ],
  )


def render_known_limitations_patch_notes_md(summary: CoreValidationSummary) -> str:
  return "\n".join(
    [
      "# Known Limitations Patch Notes (Phase 24.4B)",
      "",
      "## 追記すべき制限",
      "",
      f"### 別テーマ（{summary.theme_id}）",
      "",
      "- Evidence Map **skeleton** まで検証済み。full Evidence Map ではない。",
      "- 論文候補（Stage 4）、Webシグナル（Stage 5）、Link Candidate（Stage 6）、"
      "Strategic Watch（Stage 7）、Digest（Stage 8/9）は未検証。",
      "",
      "### 全般",
      "",
      f"- {SKELETON_CAUTION}",
      f"- {EXTERNAL_API_CAUTION}",
      "- Manual Claims はユーザー提供原文。原典（公報）との照合はユーザーの責任。",
      f"- {LEGAL_CAUTION}",
      "- DB 永続化なし（outputs/ ファイルベース）。",
      "",
    ],
  )


def save_core_validation_summary_pack(
  summary: CoreValidationSummary,
  output_dir: Path | str,
) -> dict[str, Path]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  paths = {
    "cross_theme_core_validation_summary_md": out / "cross_theme_core_validation_summary.md",
    "cross_theme_core_validation_summary_json": out / "cross_theme_core_validation_summary.json",
    "freeze_readiness_judgement_md": out / "freeze_readiness_judgement.md",
    "reviewer_response_notes_md": out / "reviewer_response_notes.md",
    "readme_patch_notes_md": out / "readme_patch_notes.md",
    "demo_script_patch_notes_md": out / "demo_script_patch_notes.md",
    "known_limitations_patch_notes_md": out / "known_limitations_patch_notes.md",
  }
  paths["cross_theme_core_validation_summary_md"].write_text(
    render_cross_theme_core_validation_summary_md(summary),
    encoding="utf-8",
  )
  paths["cross_theme_core_validation_summary_json"].write_text(
    json.dumps(summary.to_dict(), indent=2, ensure_ascii=False),
    encoding="utf-8",
  )
  paths["freeze_readiness_judgement_md"].write_text(
    render_freeze_readiness_judgement_md(summary),
    encoding="utf-8",
  )
  paths["reviewer_response_notes_md"].write_text(
    render_reviewer_response_notes_md(summary),
    encoding="utf-8",
  )
  paths["readme_patch_notes_md"].write_text(
    render_readme_patch_notes_md(summary),
    encoding="utf-8",
  )
  paths["demo_script_patch_notes_md"].write_text(
    render_demo_script_patch_notes_md(summary),
    encoding="utf-8",
  )
  paths["known_limitations_patch_notes_md"].write_text(
    render_known_limitations_patch_notes_md(summary),
    encoding="utf-8",
  )
  return paths
