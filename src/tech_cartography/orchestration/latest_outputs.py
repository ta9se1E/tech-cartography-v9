"""Helpers to track latest pipeline run and artifact index without symlinks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.orchestration.pipeline_manifest import PipelineManifest
from tech_cartography.orchestration.stage_artifacts import PRIMARY_ARTIFACT_KEYS, collect_primary_artifacts


def write_latest_run_pointer(run_id: str, manifest_path: str, output_root: str) -> str:
  """
  Write outputs/latest_run.json pointer.

  - No symlinks (JSON pointer only)
  - output_root may be outputs/pipeline_runs; pointer is written under outputs/
  """
  root = Path(output_root)
  outputs_root = root.parent if root.name != "outputs" else root
  pointer_path = outputs_root / "latest_run.json"
  payload = {"run_id": run_id, "manifest_path": manifest_path}
  pointer_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
  return str(pointer_path)


def read_latest_run_pointer(output_root: str) -> dict[str, Any] | None:
  root = Path(output_root)
  outputs_root = root.parent if root.name != "outputs" else root
  pointer_path = outputs_root / "latest_run.json"
  if not pointer_path.exists():
    return None
  data = json.loads(pointer_path.read_text(encoding="utf-8"))
  return data if isinstance(data, dict) else None


def build_artifact_index(manifest: PipelineManifest, known_outputs: dict[str, Any] | None = None) -> dict[str, Any]:
  known_outputs = known_outputs or {}
  stages = []
  for stage in manifest.stage_results:
    stages.append(
      {
        "stage_id": stage.stage_id,
        "stage_name": stage.stage_name,
        "status": stage.status,
        "input_paths": stage.input_paths,
        "output_paths": stage.output_paths,
        "skipped_reason": stage.skipped_reason,
      },
    )
  primary_artifacts = collect_primary_artifacts(known_outputs, manifest.final_outputs)
  return {
    "run_id": manifest.run_id,
    "run_name": manifest.run_name,
    "theme": manifest.theme,
    "manifest_path": manifest.config.get("manifest_path"),
    "final_outputs": manifest.final_outputs,
    "primary_artifacts": primary_artifacts,
    "stages": stages,
  }


def render_artifact_index_markdown(index: dict[str, Any]) -> str:
  lines = [
    "# Artifact Index",
    "",
    f"- run_id: {index.get('run_id')}",
    f"- run_name: {index.get('run_name')}",
    f"- theme: {index.get('theme')}",
    "",
    "## Final Outputs",
    "",
  ]
  for key, value in (index.get("final_outputs") or {}).items():
    lines.append(f"- {key}: {value}")

  lines.extend(["", "## Primary Artifacts", ""])
  for key in PRIMARY_ARTIFACT_KEYS:
    value = (index.get("primary_artifacts") or {}).get(key, "missing")
    lines.append(f"- {key}: {value}")

  lines.extend(["", "## Stages", ""])
  for stage in index.get("stages", []):
    lines.append(f"### {stage.get('stage_id')} — {stage.get('status')}")
    if stage.get("skipped_reason"):
      lines.append(f"- skipped_reason: {stage.get('skipped_reason')}")
    out_paths = stage.get("output_paths") or {}
    if out_paths:
      lines.append("- outputs:")
      for key, value in out_paths.items():
        lines.append(f"  - {key}: {value}")
    lines.append("")

  return "\n".join(lines)


def save_artifact_index(index: dict[str, Any], output_dir: str) -> str:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  json_path = out / "artifact_index.json"
  md_path = out / "artifact_index.md"
  json_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
  md_path.write_text(render_artifact_index_markdown(index), encoding="utf-8")
  return str(md_path)

