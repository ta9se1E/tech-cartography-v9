"""Readiness checks for v9 patent BigQuery SQL preview and dry-run."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.services.v8_bigquery_safety import BigQuerySafetyConfig  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402
from services_v9.patent_bigquery_query import (  # noqa: E402
  build_patent_bigquery_preview,
  run_patent_bigquery_dry_run,
  save_patent_dry_run_artifacts,
  validate_patent_bigquery_request,
)
from services_v9.search_plan import build_unified_search_plan  # noqa: E402


class _FakeJobConfig:
  def __init__(self, *, dry_run: bool, maximum_bytes_billed: int) -> None:
    self.dry_run = dry_run
    self.maximum_bytes_billed = maximum_bytes_billed


class _FakeJob:
  def __init__(self, total_bytes_processed: int = 100_000_000) -> None:
    self.total_bytes_processed = total_bytes_processed
    self.job_id = "fake-job"


class _FakeClient:
  def __init__(self, total_bytes_processed: int = 100_000_000) -> None:
    self.total_bytes_processed = total_bytes_processed

  def query(self, sql: str, job_config=None):  # noqa: ANN001
    return _FakeJob(self.total_bytes_processed)


def _profile() -> dict:
  return {
    "schema_version": "v9.2",
    "theme_name": "PAN系炭素繊維前駆体の欠陥制御",
    "theme_description": "前駆体の表面欠陥と内部ボイドを監視する",
    "keywords": {
      "core_en": ["PAN carbon fiber precursor", "surface defect"],
      "core_ja": ["PAN系炭素繊維前駆体", "表面欠陥"],
      "application_en": ["CFRP"],
      "application_ja": ["複合材補強"],
      "material_process_en": ["coagulation bath"],
      "material_process_ja": ["凝固浴"],
      "exclude_en": ["graphene"],
      "exclude_ja": ["汎用ニュース"],
    },
    "seed_publications": ["JP2022090764A"],
    "candidate_publications": ["JP2018141251A"],
    "target_companies": ["東レ", "Mitsubishi Chemical"],
    "countries": ["JP", "US"],
    "source_types": ["patent", "paper", "web", "company"],
    "cadence": "weekly",
    "priority_rules": [],
    "notes": "",
  }


def _config() -> BigQuerySafetyConfig:
  return BigQuerySafetyConfig(
    enable_bigquery_run=True,
    show_bigquery_admin=True,
    bigquery_project_id="test-project",
    bigquery_location="US",
    bigquery_max_bytes_billed=500_000_000,
    bigquery_default_limit=1000,
    bigquery_dry_run_only=True,
    bigquery_allow_execute=False,
  )


def main() -> int:
  errors: list[str] = []

  plan = build_unified_search_plan(_profile())
  preview = build_patent_bigquery_preview(plan, _profile(), config=_config())
  if not preview["sql"]:
    errors.append("SQL preview を生成できません")
  if "@include_terms" not in preview["sql"] or "@seed_publications" not in preview["sql"]:
    errors.append("parameterized SQL になっていません")
  if "claims" in preview["sql"].lower() or "description" in preview["sql"].lower():
    errors.append("claims/description を取得しようとしています")
  if validate_patent_bigquery_request(preview["request"], preview["sql"]) != [{"status": "ok", "message": "validation passed"}]:
    errors.append("query validation が通りません")

  dry_run = run_patent_bigquery_dry_run(
    preview,
    client_factory=lambda project_id, location: _FakeClient(120_000_000),
    job_config_builder=lambda payload, dry_run: _FakeJobConfig(
      dry_run=dry_run,
      maximum_bytes_billed=int(payload["maximum_bytes_billed"]),
    ),
    config=_config(),
  )
  if dry_run["dry_run_status"] != "ok":
    errors.append("dry-run が成功しません")
  if dry_run["execution_allowed"] is not False:
    errors.append("Phase v9-5B1 で本実行が許可されています")

  with tempfile.TemporaryDirectory() as tmp_dir_name:
    paths = save_patent_dry_run_artifacts(preview, dry_run, base_dir=Path(tmp_dir_name) / "v9_runs")
    if not all(path.exists() for key, path in paths.items() if key != "run_dir"):
      errors.append("artifact 保存に失敗しました")
    payload = json.loads(paths["dry_run_json"].read_text(encoding="utf-8"))
    if payload.get("dry_run_status") != "ok":
      errors.append("saved dry-run json が不正です")

  tabs_source = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")
  required_labels = ["Patent BigQuery SQL Preview", "特許BigQuery dry-runを実行", "SQL Preview", "query validation"]
  if not all(label in tabs_source for label in required_labels):
    errors.append("情報源タブの特許BigQuery UI が不足しています")

  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  if not any(button.label == "特許BigQuery dry-runを実行" for button in at.button):
    errors.append("Streamlit UI で dry-run ボタンを検出できません")

  if errors:
    print("[v9 patent bigquery dry run readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 patent bigquery dry run readiness] OK: patent BigQuery SQL preview and dry-run are ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
