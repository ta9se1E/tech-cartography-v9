"""Local scheduler config generation for weekly digest (Phase 24.3)."""

from __future__ import annotations

import plistlib
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SchedulerConfig:
  project_dir: Path
  python_bin: Path
  publication_number: str
  recipient_config: str
  recipient_group: str
  output_dir: str
  weekday: int
  hour: int
  minute: int
  timezone: str
  enable_send: bool
  label: str
  allow_repeat_this_week: bool
  include_zip: bool = True


def _scheduler_dir(output_dir: Path) -> Path:
  return output_dir / "scheduler"


def _scheduler_logs_dir(output_dir: Path) -> Path:
  return output_dir / "scheduler_logs"


def build_scheduler_wrapper_script(config: SchedulerConfig) -> str:
  project_dir = str(config.project_dir.resolve())
  python_bin = str(config.python_bin)
  recipient_config = config.recipient_config
  lines = [
    "#!/bin/bash",
    "set -euo pipefail",
    "",
    f'PROJECT_DIR="{project_dir}"',
    f'PYTHON_BIN="{python_bin}"',
    "",
    'cd "$PROJECT_DIR"',
    "",
    'if [ -f ".env" ]; then',
    "  set -a",
    '  source ".env"',
    "  set +a",
    "fi",
    "",
    '"$PYTHON_BIN" scripts/run_weekly_digest_job.py \\',
    f'  --publication-number {config.publication_number} \\',
    f'  --recipient-config {recipient_config} \\',
    f'  --recipient-group {config.recipient_group} \\',
    f'  --output-dir {config.output_dir} \\',
    "  --build-draft \\",
  ]
  if config.include_zip:
    lines.append("  --include-zip \\")
  if config.allow_repeat_this_week:
    lines.append("  --allow-repeat-this-week \\")
  if config.enable_send:
    lines.append("  --send-email \\")
  if lines[-1].endswith(" \\"):
    lines[-1] = lines[-1].rstrip(" \\")
  lines.append("")
  return "\n".join(lines)


def build_launchd_plist(config: SchedulerConfig, wrapper_script_path: Path) -> dict[str, Any]:
  out = Path(config.output_dir)
  if not out.is_absolute():
    out = config.project_dir / out
  logs_dir = _scheduler_logs_dir(out)
  return {
    "Label": config.label,
    "ProgramArguments": ["/bin/bash", str(wrapper_script_path.resolve())],
    "WorkingDirectory": str(config.project_dir.resolve()),
    "StandardOutPath": str((logs_dir / "weekly_digest_stdout.log").resolve()),
    "StandardErrorPath": str((logs_dir / "weekly_digest_stderr.log").resolve()),
    "StartCalendarInterval": {
      "Weekday": int(config.weekday),
      "Hour": int(config.hour),
      "Minute": int(config.minute),
    },
  }


def build_cron_line(config: SchedulerConfig) -> str:
  project_dir = str(config.project_dir.resolve())
  python_bin = str(config.python_bin)
  minute = int(config.minute)
  hour = int(config.hour)
  weekday = int(config.weekday)
  job_args = [
    f'"{python_bin}" scripts/run_weekly_digest_job.py',
    f"--publication-number {config.publication_number}",
    f"--recipient-config {config.recipient_config}",
    f"--recipient-group {config.recipient_group}",
    f"--output-dir {config.output_dir}",
    "--build-draft",
  ]
  if config.include_zip:
    job_args.append("--include-zip")
  if config.allow_repeat_this_week:
    job_args.append("--allow-repeat-this-week")
  if config.enable_send:
    job_args.append("--send-email")
  job_cmd = " ".join(job_args)
  shell_cmd = f'cd "{project_dir}" && set -a && source .env && set +a && {job_cmd}'
  return f"{minute} {hour} * * {weekday} {shell_cmd}"


def render_scheduler_readme(config: SchedulerConfig, paths: dict[str, Path]) -> str:
  send_mode = "送信あり（--enable-send）" if config.enable_send else "下書きのみ（デフォルト）"
  return "\n".join(
    [
      "# Weekly Digest Scheduler (Phase 24.3)",
      "",
      "## 概要",
      "",
      "ローカルMacで週次Digestジョブを実行するための設定ファイルです。",
      "launchdは `.env` を自動読み込みしないため、wrapper script経由で実行します。",
      "",
      "## 現在の設定",
      "",
      f"- 対象特許: {config.publication_number}",
      f"- 宛先グループ: {config.recipient_group}",
      f"- スケジュール: 曜日={config.weekday}（0/7=日, 1=月） {config.hour:02d}:{config.minute:02d}",
      f"- タイムゾーン: {config.timezone}",
      f"- 実行モード: {send_mode}",
      f"- Label: {config.label}",
      "",
      "## 生成ファイル",
      "",
      f"- plist: `{paths.get('launchd_plist', '')}`",
      f"- wrapper: `{paths.get('wrapper_script', '')}`",
      f"- cron sample: `{paths.get('cron_sample', '')}`",
      "",
      "## 手動実行（draft-only）",
      "",
      "```bash",
      f"bash {paths.get('wrapper_script', 'outputs/delivery/scheduler/run_weekly_digest_job.sh')}",
      "```",
      "",
      "## launchd 登録（CLI明示のみ）",
      "",
      "```bash",
      "python scripts/install_weekly_digest_schedule.py \\",
      f"  --publication-number {config.publication_number} \\",
      f"  --recipient-config {config.recipient_config} \\",
      f"  --recipient-group {config.recipient_group} \\",
      "  --install --yes",
      "```",
      "",
      "## launchd 解除（環境によりコマンドが異なる場合があります）",
      "",
      "```bash",
      f"launchctl unload ~/Library/LaunchAgents/{config.label}.plist",
      "```",
      "",
      "## 注意",
      "",
      "- UIからスケジュール登録・送信は行いません",
      "- デフォルトは下書き作成のみ（--send-email なし）",
      "- 実送信には install 時に `--enable-send` が必要",
      "- 同一週の重複送信は `allow_repeat_this_week=False` で防止",
      "- Cloud Run / Cloud Scheduler はこの Phase では未実装",
      "",
    ],
  )


def save_scheduler_wrapper_script(config: SchedulerConfig, output_dir: Path) -> Path:
  sched_dir = _scheduler_dir(output_dir)
  sched_dir.mkdir(parents=True, exist_ok=True)
  path = sched_dir / "run_weekly_digest_job.sh"
  path.write_text(build_scheduler_wrapper_script(config), encoding="utf-8")
  path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
  return path


def save_launchd_plist(
  config: SchedulerConfig,
  output_dir: Path,
  wrapper_script_path: Path,
) -> Path:
  sched_dir = _scheduler_dir(output_dir)
  sched_dir.mkdir(parents=True, exist_ok=True)
  plist_data = build_launchd_plist(config, wrapper_script_path)
  path = sched_dir / f"{config.label}.plist"
  with path.open("wb") as handle:
    plistlib.dump(plist_data, handle)
  return path


def save_cron_sample(config: SchedulerConfig, output_dir: Path) -> Path:
  sched_dir = _scheduler_dir(output_dir)
  sched_dir.mkdir(parents=True, exist_ok=True)
  path = sched_dir / "weekly_digest_cron_sample.txt"
  path.write_text(build_cron_line(config) + "\n", encoding="utf-8")
  return path


def save_scheduler_readme(
  config: SchedulerConfig,
  output_dir: Path,
  paths: dict[str, Path],
) -> Path:
  sched_dir = _scheduler_dir(output_dir)
  sched_dir.mkdir(parents=True, exist_ok=True)
  readme = sched_dir / "scheduler_readme.md"
  readme.write_text(render_scheduler_readme(config, paths), encoding="utf-8")
  return readme


def save_scheduler_bundle(config: SchedulerConfig) -> dict[str, Path]:
  out = Path(config.output_dir)
  if not out.is_absolute():
    out = config.project_dir / out
  _scheduler_logs_dir(out).mkdir(parents=True, exist_ok=True)

  wrapper = save_scheduler_wrapper_script(config, out)
  plist = save_launchd_plist(config, out, wrapper)
  cron = save_cron_sample(config, out)
  paths = {
    "wrapper_script": wrapper,
    "launchd_plist": plist,
    "cron_sample": cron,
  }
  readme = save_scheduler_readme(config, out, paths)
  paths["scheduler_readme"] = readme
  return paths
