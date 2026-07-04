"""Readiness checks for the v9 weekly scheduler."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.retrieval_run_store import build_retrieval_run_manifest, save_retrieval_run_manifest  # noqa: E402
from services_v9.watch_profile_schema import migrate_watch_profile  # noqa: E402
from services_v9.weekly_run_config import default_weekly_run_config, validate_weekly_run_config  # noqa: E402
from services_v9.weekly_scheduler import (  # noqa: E402
  acquire_weekly_run_lock,
  build_cron_preview,
  build_launchd_preview,
  release_weekly_run_lock,
  run_weekly_watch,
)


def _watch_profile() -> dict[str, object]:
  return {
    "theme_name": "全固体電池ウォッチ",
    "theme_description": "Battery materials and manufacturing signals.",
    "keywords": {
      "core_en": ["solid state battery", "cathode"],
      "core_ja": ["全固体電池", "正極材"],
      "application_en": ["energy density"],
      "application_ja": ["高エネルギー密度"],
      "material_process_en": ["electrolyte"],
      "material_process_ja": ["電解質"],
      "exclude_en": [],
      "exclude_ja": [],
    },
    "target_companies": ["Toyota", "Samsung"],
    "source_types": ["patent", "paper", "web", "company"],
  }


def _write_artifact(root: Path, source_type: str, run_id: str, rows: list[dict]) -> Path:
  mapping = {
    "patent": ("patent_retrieval_runs", "patent_candidates_staged.json"),
    "paper": ("paper_retrieval_runs", "paper_candidates_staged.json"),
    "web_company": ("web_company_retrieval_runs", "web_company_candidates_staged.json"),
  }
  subdir, filename = mapping[source_type]
  target = root / subdir / run_id
  target.mkdir(parents=True, exist_ok=True)
  (target / filename).write_text(
    json.dumps({"retrieval_run_id": run_id, "provider_status": "success", "rows": rows}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )
  return target


def main() -> None:
  config = default_weekly_run_config()
  validation = validate_weekly_run_config(config)
  assert validation["status"] == "ok"
  assert config["enabled"] is False
  assert config["execution"]["dry_run"] is True

  with tempfile.TemporaryDirectory() as tmp_dir:
    root = Path(tmp_dir)
    watch_profile_path = root / "watch_profile.json"
    watch_profile = _watch_profile()
    watch_profile_path.write_text(json.dumps(watch_profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    patent_rows = [{
      "publication_number": "US2024000001A1",
      "family_id": "FAM1",
      "title": "Solid state battery patent",
      "abstract": "electrolyte cathode process",
      "assignee": "Toyota",
      "publication_date": "2026-05-12",
      "country": "US",
      "cpc_codes": "H01M",
      "source_url": "https://patents.example.com/p1",
      "query_id": "patent_q01",
      "retrieval_run_id": "patent_saved_run",
      "provider_status": "success",
      "record_stage": "staged",
      "retrieval_mode": "real",
      "data_source": "bigquery_patent",
    }]
    paper_rows = [{
      "work_id": "https://openalex.org/W1",
      "doi": "10.1000/test1",
      "title": "Solid state battery paper",
      "abstract": "electrolyte cathode",
      "authors": ["Alice"],
      "institutions": ["Example University"],
      "publication_date": "2025-12-01",
      "source_journal": "Battery Journal",
      "cited_by_count": 12,
      "topics": ["Solid electrolytes"],
      "open_access": True,
      "original_language": "en",
      "source_url": "https://example.org/paper1",
      "query_id": "paper_q01",
      "retrieval_run_id": "paper_saved_run",
      "provider_status": "success",
      "record_stage": "staged",
      "retrieval_mode": "real",
    }]
    web_rows = [{
      "candidate_id": "w1",
      "query_id": "gw_q001",
      "country_region": "JP",
      "web_intent": "research_development",
      "result_bucket": "web",
      "original_title": "Toyota 全固体電池 研究開発",
      "original_snippet": "研究開発の更新",
      "original_language": "ja",
      "source_url": "https://example.co.jp/news/a",
      "canonical_url": "https://example.co.jp/news/a",
      "event_type": "research_development",
      "organization": "Toyota",
      "source_quality": "medium_high",
      "content_access": "full",
      "content_hash": "hash1",
      "same_story_group": "story_A",
      "summary_ja": "Toyotaの研究開発更新",
      "retrieval_run_id": "web_saved_run",
      "provider_status": "partial_success",
      "record_stage": "staged",
      "retrieval_mode": "real",
    }]

    patent_dir = _write_artifact(root, "patent", "patent_saved_run", patent_rows)
    paper_dir = _write_artifact(root, "paper", "paper_saved_run", paper_rows)
    web_dir = _write_artifact(root, "web_company", "web_saved_run", web_rows)
    manifest = build_retrieval_run_manifest(
      migrate_watch_profile(watch_profile),
      {
        "patent": {"run_id": "patent_saved_run", "artifact_dir": str(patent_dir), "status": "success", "candidate_count": 1},
        "paper": {"run_id": "paper_saved_run", "artifact_dir": str(paper_dir), "status": "success", "candidate_count": 1},
        "web_company": {"run_id": "web_saved_run", "artifact_dir": str(web_dir), "status": "partial_success", "candidate_count": 1},
      },
    )
    save_retrieval_run_manifest(manifest, base_dir=root)

    scheduler_config = default_weekly_run_config()
    scheduler_config["enabled"] = True
    scheduler_config["watch_profile_path"] = str(watch_profile_path)
    scheduler_config["execution"]["dry_run"] = True
    scheduler_config["execution"]["patent_enabled"] = True
    scheduler_config["execution"]["paper_enabled"] = True
    scheduler_config["execution"]["web_company_enabled"] = True
    scheduler_config["_config_path"] = str(root / "weekly_config.json")

    result = run_weekly_watch(
      scheduler_config,
      output_root=root,
      provider_adapters={
        "patent": lambda **kwargs: (_ for _ in ()).throw(AssertionError("dry-run patent must not execute")),
        "paper": lambda **kwargs: (_ for _ in ()).throw(AssertionError("dry-run paper must not execute")),
        "web_company": lambda **kwargs: (_ for _ in ()).throw(AssertionError("dry-run web must not execute")),
      },
    )
    assert result["status"] == "partial_success"
    run_dir = Path(result["run_dir"])
    assert (run_dir / "retrieval_run_manifest.json").exists()
    assert (run_dir / "integrated_signals.json").exists()
    assert (run_dir / "weekly_diff.json").exists()
    assert (run_dir / "weekly_digest.md").exists()
    assert (run_dir / "email_preview.json").exists()

    lock = acquire_weekly_run_lock("a" * 64, "run-lock", root / "weekly_locks", stale_timeout_seconds=60)
    assert lock["acquired"] is True
    release_weekly_run_lock(lock)

    cron_preview = build_cron_preview(scheduler_config, PROJECT_ROOT, sys.executable)
    launchd_preview = build_launchd_preview(scheduler_config, PROJECT_ROOT, sys.executable)
    assert "scripts/run_v9_weekly_watch.py --config" in cron_preview
    assert "<plist version=\"1.0\">" in launchd_preview

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    imports = subprocess.run(
      [sys.executable, "-c", "import services_v9.weekly_scheduler; import app; print('scheduler startup ok')"],
      cwd=str(PROJECT_ROOT),
      env=env,
      capture_output=True,
      text=True,
      check=True,
    )
    assert "scheduler startup ok" in imports.stdout

  print("[v9 scheduler readiness] OK: weekly signal watch scheduler is ready.")


if __name__ == "__main__":
  main()
