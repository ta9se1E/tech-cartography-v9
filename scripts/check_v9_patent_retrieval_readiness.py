"""Readiness checks for v9 patent retrieval execution and staging."""

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
  execute_patent_bigquery_retrieval,
  run_patent_bigquery_dry_run,
  save_patent_retrieval_artifacts,
)
from services_v9.search_plan import build_unified_search_plan  # noqa: E402


class _FakeJobConfig:
  def __init__(self, *, dry_run: bool, maximum_bytes_billed: int) -> None:
    self.dry_run = dry_run
    self.maximum_bytes_billed = maximum_bytes_billed


class _FakeDryRunJob:
  def __init__(self, total_bytes_processed: int = 100_000_000) -> None:
    self.total_bytes_processed = total_bytes_processed
    self.job_id = "fake-dry-run-job"


class _FakeResult:
  def __init__(self, rows: list[dict], fail_after: int | None = None) -> None:
    self.rows = list(rows)
    self.fail_after = fail_after

  def __iter__(self):
    for index, row in enumerate(self.rows):
      if self.fail_after is not None and index >= self.fail_after:
        raise RuntimeError("partial failure during iteration")
      yield row


class _FakeExecuteJob:
  def __init__(self, rows: list[dict], fail_after: int | None = None) -> None:
    self.job_id = "fake-execute-job"
    self._rows = rows
    self._fail_after = fail_after

  def result(self):
    return _FakeResult(self._rows, fail_after=self._fail_after)


class _FakeClient:
  def __init__(self, *, dry_run_bytes: int = 100_000_000, execute_rows: list[dict] | None = None, fail_after: int | None = None) -> None:
    self.dry_run_bytes = dry_run_bytes
    self.execute_rows = execute_rows or []
    self.fail_after = fail_after

  def query(self, sql: str, job_config=None):  # noqa: ANN001
    if getattr(job_config, "dry_run", False):
      return _FakeDryRunJob(self.dry_run_bytes)
    return _FakeExecuteJob(self.execute_rows, fail_after=self.fail_after)


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
    bigquery_dry_run_only=False,
    bigquery_allow_execute=True,
  )


def main() -> int:
  errors: list[str] = []

  plan = build_unified_search_plan(_profile())
  preview = build_patent_bigquery_preview(plan, _profile(), config=_config())
  dry_run = run_patent_bigquery_dry_run(
    preview,
    client_factory=lambda project_id, location: _FakeClient(dry_run_bytes=120_000_000),
    job_config_builder=lambda payload, dry_run: _FakeJobConfig(
      dry_run=dry_run,
      maximum_bytes_billed=int(payload["maximum_bytes_billed"]),
    ),
    config=_config(),
  )
  if dry_run["dry_run_status"] != "ok":
    errors.append("dry-run 成功結果を生成できません")

  blocked = execute_patent_bigquery_retrieval(preview, dry_run, approved=False, config=_config())
  if blocked["provider_status"] != "not_approved":
    errors.append("承認なし execute を拒否できません")

  success = execute_patent_bigquery_retrieval(
    preview,
    dry_run,
    approved=True,
    client_factory=lambda project_id, location: _FakeClient(
      execute_rows=[
        {
          "publication_number": "US-2024-000001-A1",
          "family_id": "FAM-1",
          "title": "PAN precursor fiber",
          "abstract": "metadata only",
          "assignee": "TORAY",
          "inventor": "Inventor A",
          "publication_date": "20240101",
          "priority_date": "20230101",
          "country": "US",
          "cpc_codes": "D01F",
          "source_url": "https://example.com/1",
        }
      ],
    ),
    job_config_builder=lambda payload, dry_run: _FakeJobConfig(
      dry_run=dry_run,
      maximum_bytes_billed=int(payload["maximum_bytes_billed"]),
    ),
    config=_config(),
  )
  if success["provider_status"] != "success":
    errors.append("承認済み execute に成功しません")
  if success["rows_retrieved"] != 1 or success["rows"][0]["record_stage"] != "staged":
    errors.append("staging 形式の特許候補を保存できません")

  partial = execute_patent_bigquery_retrieval(
    preview,
    dry_run,
    approved=True,
    client_factory=lambda project_id, location: _FakeClient(
      execute_rows=[
        {"publication_number": "US-1", "family_id": "FAM-1", "title": "A", "abstract": "a"},
        {"publication_number": "US-2", "family_id": "FAM-2", "title": "B", "abstract": "b"},
      ],
      fail_after=1,
    ),
    job_config_builder=lambda payload, dry_run: _FakeJobConfig(
      dry_run=dry_run,
      maximum_bytes_billed=int(payload["maximum_bytes_billed"]),
    ),
    config=_config(),
  )
  if partial["provider_status"] != "partial_success" or partial["rows_retrieved"] != 1:
    errors.append("partial success 時に部分成果物を保持できません")

  with tempfile.TemporaryDirectory() as tmp_dir_name:
    paths = save_patent_retrieval_artifacts(preview, dry_run, partial, base_dir=Path(tmp_dir_name) / "v9_runs")
    if not paths["staged_json"].exists() or not paths["staged_csv"].exists() or not paths["retrieval_log_json"].exists():
      errors.append("retrieval artifact を保存できません")
    payload = json.loads(paths["staged_json"].read_text(encoding="utf-8"))
    if payload.get("provider_status") != "partial_success":
      errors.append("partial success の provider_status を保存できません")

  tabs_source = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")
  required_labels = ["このqueryを承認", "承認済み特許取得を実行", "provider status", "retrieval_run_id"]
  if not all(label in tabs_source for label in required_labels):
    errors.append("特許取得 execute UI が不足しています")

  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  button_labels = [button.label for button in at.button]
  if "このqueryを承認" not in button_labels or "承認済み特許取得を実行" not in button_labels:
    errors.append("Streamlit UI で approval/execute ボタンを検出できません")

  if errors:
    print("[v9 patent retrieval readiness] NG:")
    for error in errors:
      print(f"- {error}")
    return 1

  print("[v9 patent retrieval readiness] OK: approved patent retrieval and staging are ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
