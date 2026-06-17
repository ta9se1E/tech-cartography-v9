from __future__ import annotations

import csv
import json
from pathlib import Path

import tech_cartography.orchestration.case_study_runner as runner
from tech_cartography.orchestration.pipeline_config import PipelineConfig


def _write_light_csv(path: Path, rows: list[dict] | None = None) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  rows = rows or [
    {
      "publication_number": "US1",
      "title": "Carbon fiber",
      "assignee": "TORAY",
      "abstract": "prepreg",
    },
  ]
  with path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)


def test_safe_run_blocks_clustering_without_existing_csv(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.chdir(tmp_path)
  (tmp_path / "outputs").mkdir()

  cfg = PipelineConfig(
    theme="test",
    run_name="demo",
    output_root="outputs/pipeline_runs",
    execute_bigquery=False,
  )

  monkeypatch.setitem(runner.STAGE_RUNNERS, "search_strategy", lambda c, d, p: {
    "status": "ok",
    "paths": {"search_strategy_json": str(Path(d) / "search_strategy.json")},
    "summary": {},
  })

  result = runner.run_carbon_fiber_evidence_map_pipeline(cfg)
  statuses = result["stage_statuses"]
  assert statuses["search_strategy"] == "success"
  assert statuses["bigquery_light_retrieval"] == "skipped"
  assert statuses["technology_clustering_ranking"] == "blocked"
  assert statuses["top5_fulltext_collection"] == "blocked"

  summary_md = Path(result["manifest_path"]).parent / "run_summary.md"
  assert "Next Recommended Command" in summary_md.read_text(encoding="utf-8")


def test_execute_bigquery_passes_dedup_csv_to_clustering(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.chdir(tmp_path)
  (tmp_path / "outputs").mkdir()
  dedup = tmp_path / "dedup.csv"
  _write_light_csv(dedup)

  cfg = PipelineConfig(
    theme="test",
    output_root="outputs/pipeline_runs",
    execute_bigquery=True,
    stop_stage="technology_clustering_ranking",
  )
  clustering_called: list[str] = []

  def _bq(_c, _d, _p):
    return {
      "status": "ok",
      "result": {
        "output_csv_path": str(dedup),
        "output_raw_csv_path": str(tmp_path / "raw.csv"),
        "output_summary_path": str(tmp_path / "summary.json"),
      },
      "paths": {},
      "summary": {"total_records_after_dedup": 1},
    }

  def _cluster(_c, _d, prev):
    clustering_called.append(prev.get("bigquery_light_dedup_csv", ""))
    return {"status": "ok", "paths": {"top20_patents_csv": str(Path(_d) / "top20.csv")}, "summary": {}}

  monkeypatch.setitem(runner.STAGE_RUNNERS, "search_strategy", lambda c, d, p: {
    "status": "ok",
    "paths": {"search_strategy_json": str(Path(d) / "search_strategy.json")},
    "summary": {},
  })
  monkeypatch.setitem(runner.STAGE_RUNNERS, "bigquery_light_retrieval", _bq)
  monkeypatch.setitem(runner.STAGE_RUNNERS, "technology_clustering_ranking", _cluster)

  result = runner.run_carbon_fiber_evidence_map_pipeline(cfg)
  assert result["stage_statuses"]["bigquery_light_retrieval"] == "success"
  assert result["stage_statuses"]["technology_clustering_ranking"] == "success"
  assert clustering_called == [str(dedup)]
  assert result["stage_statuses"]["top5_fulltext_collection"] == "skipped"


def test_use_existing_light_csv_skips_bigquery_and_runs_clustering(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.chdir(tmp_path)
  (tmp_path / "outputs").mkdir()
  existing = tmp_path / "existing.csv"
  _write_light_csv(existing)

  cfg = PipelineConfig(
    theme="test",
    output_root="outputs/pipeline_runs",
    use_existing_light_csv=str(existing),
    stop_stage="technology_clustering_ranking",
  )
  clustering_input: list[str] = []

  def _cluster(_c, _d, prev):
    clustering_input.append(prev.get("bigquery_light_dedup_csv", ""))
    return {"status": "ok", "paths": {"top20_patents_csv": str(Path(_d) / "top20.csv")}, "summary": {}}

  monkeypatch.setitem(runner.STAGE_RUNNERS, "search_strategy", lambda c, d, p: {
    "status": "ok",
    "paths": {"search_strategy_json": str(Path(d) / "search_strategy.json")},
    "summary": {},
  })
  monkeypatch.setitem(runner.STAGE_RUNNERS, "technology_clustering_ranking", _cluster)

  result = runner.run_carbon_fiber_evidence_map_pipeline(cfg)
  assert result["stage_statuses"]["bigquery_light_retrieval"] == "skipped"
  assert result["stage_statuses"]["technology_clustering_ranking"] == "success"
  assert clustering_input == [str(existing)]


def test_bigquery_success_without_dedup_blocks_clustering(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.chdir(tmp_path)
  (tmp_path / "outputs").mkdir()

  cfg = PipelineConfig(theme="test", output_root="outputs/pipeline_runs", execute_bigquery=True)

  monkeypatch.setitem(runner.STAGE_RUNNERS, "search_strategy", lambda c, d, p: {
    "status": "ok",
    "paths": {"search_strategy_json": str(Path(d) / "search_strategy.json")},
    "summary": {},
  })
  monkeypatch.setitem(runner.STAGE_RUNNERS, "bigquery_light_retrieval", lambda c, d, p: {
    "status": "ok",
    "paths": {},
    "summary": {},
  })

  result = runner.run_carbon_fiber_evidence_map_pipeline(cfg)
  assert result["stage_statuses"]["bigquery_light_retrieval"] == "failed"
  assert result["stage_statuses"]["technology_clustering_ranking"] == "blocked"


def test_clustering_empty_csv_fails(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.chdir(tmp_path)
  empty = tmp_path / "empty.csv"
  empty.write_text("publication_number,title\n", encoding="utf-8")

  cfg = PipelineConfig(
    theme="test",
    output_root="outputs/pipeline_runs",
    use_existing_light_csv=str(empty),
    stop_stage="technology_clustering_ranking",
  )
  monkeypatch.setitem(runner.STAGE_RUNNERS, "search_strategy", lambda c, d, p: {
    "status": "ok",
    "paths": {"search_strategy_json": str(Path(d) / "search_strategy.json")},
    "summary": {},
  })

  result = runner.run_carbon_fiber_evidence_map_pipeline(cfg)
  assert result["stage_statuses"]["technology_clustering_ranking"] == "failed"


def test_clustering_missing_columns_fails(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.chdir(tmp_path)
  bad = tmp_path / "bad.csv"
  bad.write_text("title,assignee\nCarbon fiber,TORAY\n", encoding="utf-8")

  cfg = PipelineConfig(
    theme="test",
    output_root="outputs/pipeline_runs",
    use_existing_light_csv=str(bad),
    stop_stage="technology_clustering_ranking",
  )
  monkeypatch.setitem(runner.STAGE_RUNNERS, "search_strategy", lambda c, d, p: {
    "status": "ok",
    "paths": {"search_strategy_json": str(Path(d) / "search_strategy.json")},
    "summary": {},
  })

  result = runner.run_carbon_fiber_evidence_map_pipeline(cfg)
  assert result["stage_statuses"]["technology_clustering_ranking"] == "failed"


def test_fulltext_stage_dry_run_success(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.chdir(tmp_path)
  (tmp_path / "outputs").mkdir()
  existing = tmp_path / "existing.csv"
  _write_light_csv(existing)
  top5 = tmp_path / "top5.csv"
  top5.write_text(
    "publication_number,title,assignee,country,source_route\n"
    "US-12565719-B2,Carbon fiber,Toray,US,us_bigquery_fulltext_candidate\n",
    encoding="utf-8",
  )
  strategic = tmp_path / "strategic.csv"
  strategic.write_text(
    "publication_number,title,assignee,country,source_route,watch_reason_japanese\n"
    "CN-121137864-A,PAN fiber,ZHONGFU SHENYING CARBON FIBER CO LTD,CN,manual_fulltext_required,中国候補\n",
    encoding="utf-8",
  )

  cfg = PipelineConfig(
    theme="test",
    output_root="outputs/pipeline_runs",
    use_existing_light_csv=str(existing),
    stop_stage="top5_fulltext_collection",
    execute_fulltext=False,
  )

  def _cluster(_c, _d, prev):
    return {
      "status": "ok",
      "paths": {
        "top20_patents_csv": str(Path(_d) / "top20.csv"),
        "top5_fulltext_candidates_csv": str(top5),
        "strategic_watch_candidates_csv": str(strategic),
      },
      "summary": {},
    }

  def _fulltext(_c, _d, prev):
    assert prev.get("strategic_watch_candidates_csv") == str(strategic)
    out = Path(_d)
    out.mkdir(parents=True, exist_ok=True)
    manual = out / "strategic_watch_manual_fulltext_required.csv"
    manual.write_text("publication_number,country\nCN-121137864-A,CN\n", encoding="utf-8")
    return {
      "status": "ok",
      "paths": {
        "strategic_watch_manual_fulltext_required_csv": str(manual),
        "fulltext_evidence_report_md": str(out / "report.md"),
      },
      "summary": {"mode": "dry_run", "dry_run_only_count": 1},
    }

  monkeypatch.setitem(runner.STAGE_RUNNERS, "search_strategy", lambda c, d, p: {
    "status": "ok",
    "paths": {"search_strategy_json": str(Path(d) / "search_strategy.json")},
    "summary": {},
  })
  monkeypatch.setitem(runner.STAGE_RUNNERS, "technology_clustering_ranking", _cluster)
  monkeypatch.setitem(runner.STAGE_RUNNERS, "top5_fulltext_collection", _fulltext)

  result = runner.run_carbon_fiber_evidence_map_pipeline(cfg)
  assert result["stage_statuses"]["technology_clustering_ranking"] == "success"
  assert result["stage_statuses"]["top5_fulltext_collection"] == "success"


def test_evidence_validation_stage_order_and_stop(tmp_path: Path, monkeypatch) -> None:
  from tech_cartography.orchestration.stage_resolver import resolve_stage_order

  order = resolve_stage_order()
  assert order.index("evidence_validation") == order.index("top5_fulltext_collection") + 1

  monkeypatch.chdir(tmp_path)
  (tmp_path / "outputs").mkdir()
  existing = tmp_path / "existing.csv"
  _write_light_csv(existing)
  top5 = tmp_path / "top5.csv"
  top5.write_text("publication_number,title\nUS-1,Carbon\n", encoding="utf-8")
  fulltext_json = tmp_path / "fulltext.json"
  fulltext_json.write_text(
    '[{"publication_number":"US-1","country":"US","retrieval_status":"dry_run_only","evidence_level":"metadata_only"}]',
    encoding="utf-8",
  )
  manual = tmp_path / "manual.csv"
  manual.write_text("publication_number,country\nCN-1,CN\n", encoding="utf-8")

  cfg = PipelineConfig(
    theme="test",
    output_root="outputs/pipeline_runs",
    use_existing_light_csv=str(existing),
    stop_stage="evidence_validation",
    execute_fulltext=False,
  )

  def _cluster(_c, _d, prev):
    return {
      "status": "ok",
      "paths": {
        "top20_patents_csv": str(Path(_d) / "top20.csv"),
        "top5_fulltext_candidates_csv": str(top5),
      },
      "summary": {},
    }

  def _fulltext(_c, _d, prev):
    return {
      "status": "ok",
      "paths": {
        "top5_fulltext_records_json": str(fulltext_json),
        "strategic_watch_manual_fulltext_required_csv": str(manual),
      },
      "summary": {},
    }

  monkeypatch.setitem(runner.STAGE_RUNNERS, "search_strategy", lambda c, d, p: {
    "status": "ok",
    "paths": {"search_strategy_json": str(Path(d) / "search_strategy.json")},
    "summary": {},
  })
  monkeypatch.setitem(runner.STAGE_RUNNERS, "technology_clustering_ranking", _cluster)
  monkeypatch.setitem(runner.STAGE_RUNNERS, "top5_fulltext_collection", _fulltext)

  result = runner.run_carbon_fiber_evidence_map_pipeline(cfg)
  assert result["stage_statuses"]["evidence_validation"] == "success"
  assert result["stage_statuses"]["claim_element_extraction"] == "skipped"


def test_fulltext_config_passed_to_retriever(tmp_path: Path, monkeypatch) -> None:
  captured: list = []

  def _fake_retrieve(top5, cfg, strategic_watch_candidates=None, client_factory=None):  # noqa: ANN001
    captured.append(cfg)
    return {
      "status": "ok",
      "retrieved_records": [],
      "manual_required_rows": [],
      "strategic_watch_manual_rows": [],
      "plan": {"plan_summary": {}},
      "execute_preview": {},
      "execute_results": [],
      "checklist_markdown": "",
      "summary": {},
    }

  monkeypatch.setattr(
    "tech_cartography.orchestration.case_study_runner.retrieve_controlled_fulltext_run",
    _fake_retrieve,
  )
  top5_csv = tmp_path / "top5.csv"
  top5_csv.write_text(
    "publication_number,title,country,source_route\nUS-1,Fiber,US,us_bigquery_fulltext_candidate\n",
    encoding="utf-8",
  )
  cfg = PipelineConfig(
    execute_fulltext=True,
    internal_cost_policy_name="claims_check",
    fulltext_execute_limit=1,
    fulltext_publication_number="US-1",
    confirm_fulltext_execute=True,
    fulltext_scope="claims_only",
    maximum_fulltext_usd=15.0,
    allow_expensive_fulltext=True,
  )
  runner.run_fulltext_collection_stage(cfg, str(tmp_path / "out"), {"top5_fulltext_candidates_csv": str(top5_csv)})
  assert captured
  assert captured[0].execute_limit == 1
  assert captured[0].publication_number == "US-1"
  assert captured[0].confirm_fulltext_execute is True
  assert captured[0].fulltext_scope == "claims_only"
  assert captured[0].maximum_fulltext_usd == 2.5
  assert captured[0].allow_expensive_fulltext is True
  assert captured[0].internal_cost_policy is not None
  assert captured[0].internal_cost_policy.policy_name == "claims_check"


def test_evidence_validation_ready_with_retrieved_record(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.chdir(tmp_path)
  (tmp_path / "outputs").mkdir()
  existing = tmp_path / "existing.csv"
  _write_light_csv(existing)
  fulltext_json = tmp_path / "fulltext.json"
  fulltext_json.write_text(
    json.dumps(
      [
        {
          "publication_number": "US-1",
          "country": "US",
          "retrieval_status": "retrieved",
          "claims": "1. A carbon fiber bundle.",
          "description": "The bundle is manufactured by carbonization.",
          "evidence_level": "high_fulltext_evidence",
          "evidence_coverage": {
            "has_claims": True,
            "has_description": True,
            "evidence_level": "high_fulltext_evidence",
          },
        },
      ],
    ),
    encoding="utf-8",
  )

  cfg = PipelineConfig(
    theme="test",
    output_root="outputs/pipeline_runs",
    use_existing_light_csv=str(existing),
    stop_stage="evidence_validation",
  )

  def _cluster(_c, _d, prev):
    return {
      "status": "ok",
      "paths": {"top5_fulltext_candidates_csv": str(tmp_path / "top5.csv")},
      "summary": {},
    }

  def _fulltext(_c, _d, prev):
    return {
      "status": "ok",
      "paths": {"top5_fulltext_records_json": str(fulltext_json)},
      "summary": {},
    }

  (tmp_path / "top5.csv").write_text("publication_number\nUS-1\n", encoding="utf-8")
  monkeypatch.setitem(runner.STAGE_RUNNERS, "search_strategy", lambda c, d, p: {
    "status": "ok",
    "paths": {"search_strategy_json": str(Path(d) / "search_strategy.json")},
    "summary": {},
  })
  monkeypatch.setitem(runner.STAGE_RUNNERS, "technology_clustering_ranking", _cluster)
  monkeypatch.setitem(runner.STAGE_RUNNERS, "top5_fulltext_collection", _fulltext)

  result = runner.run_carbon_fiber_evidence_map_pipeline(cfg)
  assert result["stage_statuses"]["evidence_validation"] == "success"
