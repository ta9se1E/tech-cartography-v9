"""Run manifest for the one-command pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.orchestration.pipeline_config import PipelineConfig


def _now_iso() -> str:
  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class PipelineStageResult:
  stage_id: str
  stage_name: str
  status: str = "pending"
  started_at: str | None = None
  finished_at: str | None = None
  input_paths: dict[str, Any] = field(default_factory=dict)
  output_paths: dict[str, Any] = field(default_factory=dict)
  summary: dict[str, Any] = field(default_factory=dict)
  warnings: list[str] = field(default_factory=list)
  errors: list[str] = field(default_factory=list)
  skipped_reason: str | None = None

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> PipelineStageResult:
    return cls(
      stage_id=str(data.get("stage_id", "")),
      stage_name=str(data.get("stage_name", "")),
      status=str(data.get("status", "pending")),
      started_at=data.get("started_at"),
      finished_at=data.get("finished_at"),
      input_paths=dict(data.get("input_paths", {}) or {}),
      output_paths=dict(data.get("output_paths", {}) or {}),
      summary=dict(data.get("summary", {}) or {}),
      warnings=list(data.get("warnings", []) or []),
      errors=list(data.get("errors", []) or []),
      skipped_reason=data.get("skipped_reason"),
    )


@dataclass
class PipelineManifest:
  run_id: str
  run_name: str
  theme: str
  started_at: str
  finished_at: str | None = None
  status: str = "running"
  config: dict[str, Any] = field(default_factory=dict)
  stage_results: list[PipelineStageResult] = field(default_factory=list)
  final_outputs: dict[str, Any] = field(default_factory=dict)
  warnings: list[str] = field(default_factory=list)
  errors: list[str] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      **asdict(self),
      "stage_results": [stage.to_dict() for stage in self.stage_results],
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> PipelineManifest:
    stages = [
      PipelineStageResult.from_dict(item) if isinstance(item, dict) else item
      for item in data.get("stage_results", [])
    ]
    return cls(
      run_id=str(data.get("run_id", "")),
      run_name=str(data.get("run_name", "")),
      theme=str(data.get("theme", "")),
      started_at=str(data.get("started_at", "")),
      finished_at=data.get("finished_at"),
      status=str(data.get("status", "running")),
      config=dict(data.get("config", {}) or {}),
      stage_results=stages,
      final_outputs=dict(data.get("final_outputs", {}) or {}),
      warnings=list(data.get("warnings", []) or []),
      errors=list(data.get("errors", []) or []),
    )


def create_manifest(config: PipelineConfig, *, run_id: str, run_output_dir: str) -> PipelineManifest:
  run_name = config.run_name or run_id
  return PipelineManifest(
    run_id=run_id,
    run_name=run_name,
    theme=config.theme,
    started_at=_now_iso(),
    status="running",
    config={**config.to_dict(), "run_output_dir": run_output_dir},
    stage_results=[],
    final_outputs={},
    warnings=[],
    errors=[],
  )


def update_stage_result(manifest: PipelineManifest, result: PipelineStageResult) -> PipelineManifest:
  remaining = [stage for stage in manifest.stage_results if stage.stage_id != result.stage_id]
  # Keep insertion order (pipeline order is defined elsewhere).
  manifest.stage_results = remaining + [result]
  return manifest


def summarize_manifest(manifest: PipelineManifest) -> dict[str, Any]:
  counts = {"success": 0, "skipped": 0, "failed": 0, "blocked": 0, "running": 0, "pending": 0}
  for stage in manifest.stage_results:
    counts[stage.status] = counts.get(stage.status, 0) + 1
  return {
    "run_id": manifest.run_id,
    "run_name": manifest.run_name,
    "theme": manifest.theme,
    "status": manifest.status,
    "started_at": manifest.started_at,
    "finished_at": manifest.finished_at,
    "stage_counts": counts,
    "final_outputs": manifest.final_outputs,
    "warnings": manifest.warnings,
    "errors": manifest.errors,
  }


def _render_run_summary_markdown(manifest: PipelineManifest) -> str:
  summary = summarize_manifest(manifest)
  lines = [
    "# Carbon Fiber Evidence Map Pipeline Run Summary",
    "",
    f"- run_id: {summary.get('run_id')}",
    f"- run_name: {summary.get('run_name')}",
    f"- theme: {summary.get('theme')}",
    f"- status: {summary.get('status')}",
    f"- started_at: {summary.get('started_at')}",
    f"- finished_at: {summary.get('finished_at')}",
    "",
    "## Stage Table",
    "",
    "| stage_id | status | skipped_reason |",
    "| --- | --- | --- |",
  ]
  for stage in manifest.stage_results:
    reason = stage.skipped_reason or ""
    lines.append(f"| {stage.stage_id} | {stage.status} | {reason} |")

  failed_stages = [s for s in manifest.stage_results if s.status == "failed"]
  if failed_stages:
    lines.extend(["", "## Failed Stage Details", ""])
    for stage in failed_stages:
      lines.append(f"### {stage.stage_id}")
      if stage.errors:
        for err in stage.errors[:5]:
          lines.append(f"- error: {err}")
      if stage.summary.get("missing_inputs"):
        lines.append(f"- missing_inputs: {stage.summary.get('missing_inputs')}")

  blocked_stages = [s for s in manifest.stage_results if s.status == "blocked"]
  if blocked_stages:
    lines.extend(["", "## Blocked Stage Reasons", ""])
    for stage in blocked_stages:
      lines.append(f"- {stage.stage_id}: {stage.skipped_reason or 'blocked'}")

  lines.extend(["", "## Final Outputs", ""])
  for key, value in (manifest.final_outputs or {}).items():
    lines.append(f"- {key}: {value}")

  next_commands = manifest.config.get("next_recommended_commands")
  if not next_commands:
    from tech_cartography.orchestration.stage_artifacts import build_next_recommended_commands

    next_commands = build_next_recommended_commands(manifest, PipelineConfig.from_dict(manifest.config))
  if next_commands:
    lines.extend(["", "## Next Recommended Command", ""])
    for cmd in next_commands:
      lines.append(f"- `{cmd}`")

  if manifest.warnings:
    lines.extend(["", "## Warnings", ""])
    for w in manifest.warnings:
      lines.append(f"- {w}")
  if manifest.errors:
    lines.extend(["", "## Errors", ""])
    for e in manifest.errors:
      lines.append(f"- {e}")
  return "\n".join(lines)


def save_manifest(manifest: PipelineManifest, output_dir: str | Path) -> str:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  manifest_path = out / "run_manifest.json"
  with manifest_path.open("w", encoding="utf-8") as handle:
    json.dump(manifest.to_dict(), handle, indent=2, ensure_ascii=False)
  summary_path = out / "run_summary.md"
  summary_path.write_text(_render_run_summary_markdown(manifest), encoding="utf-8")
  return str(manifest_path)


def load_manifest(path: str | Path) -> PipelineManifest:
  data = json.loads(Path(path).read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError("manifest JSON must be an object")
  return PipelineManifest.from_dict(data)

