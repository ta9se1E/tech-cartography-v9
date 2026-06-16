"""Tests for Japanese labels."""

from tech_cartography.ui.japanese_labels import (
  explain_evidence_level,
  explain_source_route,
  explain_stage_status,
  translate_cluster_id,
  translate_evidence_level,
  translate_reader_action,
  translate_signal_relation,
  translate_source_route,
  translate_stage_id,
  translate_stage_status,
)


def test_cluster_id_japanese() -> None:
  assert "PAN" in translate_cluster_id("core_manufacturing")
  assert translate_cluster_id("surface_interface") != "surface_interface"


def test_source_route_japanese() -> None:
  assert "米国" in translate_source_route("us_bigquery_fulltext_candidate")
  assert "手動" in translate_source_route("manual_fulltext_required")


def test_evidence_level_japanese() -> None:
  assert "要約" in translate_evidence_level("metadata_only")
  assert explain_evidence_level("metadata_only")


def test_unknown_values_do_not_crash() -> None:
  assert translate_cluster_id("")
  assert translate_cluster_id("unknown")
  assert translate_source_route("")
  assert translate_evidence_level("nan")
  assert translate_stage_id("")
  assert translate_stage_status("unknown_status")
  assert explain_stage_status("blocked")
  assert translate_signal_relation("")
  assert translate_reader_action("")
