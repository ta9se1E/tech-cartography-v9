"""Readiness checks for v9 browser startup imports."""

from __future__ import annotations

import builtins
import importlib
import sys
import urllib.request
from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
  app_text = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
  assert "sys.path.append" not in app_text
  assert "sys.path.insert" not in app_text

  seen_imports: list[str] = []
  original_import = builtins.__import__

  def hooked_import(name, globals=None, locals=None, fromlist=(), level=0):
    seen_imports.append(name)
    return original_import(name, globals, locals, fromlist, level)

  builtins.__import__ = hooked_import
  original_urlopen = urllib.request.urlopen

  def blocked_urlopen(*args, **kwargs):
    raise AssertionError("network must not be used during startup import")

  urllib.request.urlopen = blocked_urlopen
  try:
    importlib.import_module("services_v9.demo_data")
    importlib.import_module("services_v9")
    importlib.import_module("services_v9.patent_bigquery_query")
    importlib.import_module("ui_v9.signal_watch_app")
    importlib.import_module("app")
  finally:
    builtins.__import__ = original_import
    urllib.request.urlopen = original_urlopen

  assert not any(name.startswith("tech_cartography") for name in seen_imports)
  assert not any(name.startswith("google.cloud") for name in seen_imports)

  from services_v9 import paper_openalex_retrieval
  from services_v9 import patent_bigquery_query
  from services_v9 import web_company_retrieval

  calls: list[str] = []

  def blocked_client_factory(*args, **kwargs):
    calls.append("bigquery_client")
    raise AssertionError("BigQuery client must not be created on render")

  def blocked_openalex(*args, **kwargs):
    calls.append("openalex")
    raise AssertionError("OpenAlex fetch must not run on render")

  def blocked_tavily(*args, **kwargs):
    calls.append("tavily")
    raise AssertionError("Tavily fetch must not run on render")

  def blocked_grounding(*args, **kwargs):
    calls.append("grounding")
    raise AssertionError("Grounding verify must not run on render")

  patent_original = patent_bigquery_query._default_client_factory
  openalex_original = paper_openalex_retrieval._default_open_url
  tavily_original = web_company_retrieval._default_tavily_json_post
  grounding_original = web_company_retrieval._default_google_grounding_verify
  urlopen_original = urllib.request.urlopen
  try:
    patent_bigquery_query._default_client_factory = blocked_client_factory
    paper_openalex_retrieval._default_open_url = blocked_openalex
    web_company_retrieval._default_tavily_json_post = blocked_tavily
    web_company_retrieval._default_google_grounding_verify = blocked_grounding
    urllib.request.urlopen = blocked_urlopen

    at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
    at.run()
  finally:
    patent_bigquery_query._default_client_factory = patent_original
    paper_openalex_retrieval._default_open_url = openalex_original
    web_company_retrieval._default_tavily_json_post = tavily_original
    web_company_retrieval._default_google_grounding_verify = grounding_original
    urllib.request.urlopen = urlopen_original

  assert not calls
  assert len(at.get("tab")) == 6
  assert [tab.label for tab in at.get("tab")] == [
    "テーマ設定",
    "情報源",
    "注目シグナル",
    "週次更新",
    "監視プロファイル",
    "ダイジェスト / エクスポート",
  ]
  button_labels = [button.label for button in at.button]
  assert "現在の取得runを保存" in button_labels
  assert "最新の保存済み取得結果を読み込む" in button_labels

  print("[v9 browser startup readiness] OK: app starts without legacy PYTHONPATH dependency.")


if __name__ == "__main__":
  main()
