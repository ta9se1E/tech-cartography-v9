"""Persistence for core validation and theme validation outputs (Phase 24.4)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from tech_cartography.validation.core_validation import (
  CoreValidationSummary,
  LinkScoreCalibrationSummary,
  ReproducibilityPatentStatus,
  render_core_validation_summary_md,
  render_demo_script_patch_notes,
  render_known_limitations_patch_notes,
  render_link_score_calibration_md,
  render_readme_patch_notes,
  render_reproducibility_status_md,
  build_freeze_readiness_judgement,
)
from tech_cartography.validation.theme_validation import (
  ThemeValidationResult,
  render_theme_validation_md,
)


def save_link_score_calibration(
  summary: LinkScoreCalibrationSummary,
  output_dir: Path | str,
) -> dict[str, Path]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  pub = summary.publication_number
  paths = {
    "link_score_md": out / f"link_score_calibration_summary_{pub}.md",
    "link_score_json": out / f"link_score_calibration_summary_{pub}.json",
  }
  paths["link_score_md"].write_text(render_link_score_calibration_md(summary), encoding="utf-8")
  paths["link_score_json"].write_text(
    json.dumps(summary.to_dict(), indent=2, ensure_ascii=False),
    encoding="utf-8",
  )
  return paths


def save_reproducibility_status_report(
  items: list[ReproducibilityPatentStatus],
  output_dir: Path | str,
) -> dict[str, Path]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  paths = {
    "repro_md": out / "reproducibility_status_report.md",
    "repro_json": out / "reproducibility_status_report.json",
    "repro_csv": out / "reproducibility_status_report.csv",
  }
  paths["repro_md"].write_text(render_reproducibility_status_md(items), encoding="utf-8")
  paths["repro_json"].write_text(
    json.dumps([item.to_dict() for item in items], indent=2, ensure_ascii=False),
    encoding="utf-8",
  )

  if items:
    fieldnames = list(items[0].to_dict().keys())
    with paths["repro_csv"].open("w", encoding="utf-8", newline="") as handle:
      writer = csv.DictWriter(handle, fieldnames=fieldnames)
      writer.writeheader()
      for item in items:
        writer.writerow(item.to_dict())
  else:
    paths["repro_csv"].write_text("", encoding="utf-8")

  return paths


def save_core_validation_pack(
  summary: CoreValidationSummary,
  output_dir: Path | str,
) -> dict[str, Path]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  paths: dict[str, Path] = {
    "core_summary_md": out / "core_validation_summary.md",
    "core_summary_json": out / "core_validation_summary.json",
    "freeze_judgement_md": out / "freeze_readiness_judgement.md",
    "readme_patch_md": out / "readme_patch_notes.md",
    "demo_patch_md": out / "demo_script_patch_notes.md",
    "limitations_patch_md": out / "known_limitations_patch_notes.md",
  }

  paths["core_summary_md"].write_text(render_core_validation_summary_md(summary), encoding="utf-8")
  paths["core_summary_json"].write_text(
    json.dumps(summary.to_dict(), indent=2, ensure_ascii=False),
    encoding="utf-8",
  )
  paths["freeze_judgement_md"].write_text(build_freeze_readiness_judgement(summary), encoding="utf-8")
  paths["readme_patch_md"].write_text(render_readme_patch_notes(summary), encoding="utf-8")
  paths["demo_patch_md"].write_text(render_demo_script_patch_notes(summary), encoding="utf-8")
  paths["limitations_patch_md"].write_text(render_known_limitations_patch_notes(summary), encoding="utf-8")

  for pub, cal in summary.link_calibration.items():
    link_paths = save_link_score_calibration(cal, out)
    paths[f"link_score_md_{pub}"] = link_paths["link_score_md"]
    paths[f"link_score_json_{pub}"] = link_paths["link_score_json"]

  repro_paths = save_reproducibility_status_report(summary.reproducibility, out)
  paths.update(
    {
      "repro_md": repro_paths["repro_md"],
      "repro_json": repro_paths["repro_json"],
      "repro_csv": repro_paths["repro_csv"],
    },
  )
  return paths


def save_theme_validation_report(
  result: ThemeValidationResult,
  output_dir: Path | str,
  *,
  project_root: Path | str = ".",
) -> dict[str, Path]:
  out = Path(output_dir) / result.theme_id
  out.mkdir(parents=True, exist_ok=True)
  paths = {
    "theme_report_md": out / "theme_validation_report.md",
    "theme_report_json": out / "theme_validation_report.json",
    "theme_matrix_csv": out / "theme_validation_matrix.csv",
  }

  md = render_theme_validation_md(result, project_root=project_root)
  paths["theme_report_md"].write_text(md, encoding="utf-8")
  paths["theme_report_json"].write_text(
    json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
    encoding="utf-8",
  )

  with paths["theme_matrix_csv"].open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=["stage_id", "stage_name", "status", "message"])
    writer.writeheader()
    for stage in result.stages:
      writer.writerow(stage.to_dict())

  return paths
