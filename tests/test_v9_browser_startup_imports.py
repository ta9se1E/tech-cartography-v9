"""Startup import smoke tests for v9 browser launch."""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_plain_python(code: str) -> subprocess.CompletedProcess[str]:
  env = dict(os.environ)
  env.pop("PYTHONPATH", None)
  return subprocess.run(
    [sys.executable, "-c", code],
    cwd=PROJECT_ROOT,
    env=env,
    capture_output=True,
    text=True,
    check=False,
  )


def test_plain_imports_succeed_without_pythonpath() -> None:
  cases = [
    ("services_v9.demo_data", "demo_data import OK"),
    ("services_v9", "services_v9 import OK"),
    ("services_v9.patent_bigquery_query", "patent module import OK"),
    ("ui_v9.signal_watch_app", "signal_watch_app import OK"),
    ("app", "app import OK"),
  ]
  for module_name, marker in cases:
    result = _run_plain_python(f"import {module_name}; print({marker!r})")
    assert result.returncode == 0, result.stderr
    assert marker in result.stdout


def test_plain_app_import_has_no_sys_path_hack_and_no_legacy_dependency() -> None:
  app_text = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
  assert "sys.path.append" not in app_text
  assert "sys.path.insert" not in app_text

  result = _run_plain_python(
    """
import builtins
import urllib.request

seen = []
orig_import = builtins.__import__

def hooked_import(name, globals=None, locals=None, fromlist=(), level=0):
    seen.append(name)
    return orig_import(name, globals, locals, fromlist, level)

builtins.__import__ = hooked_import

def blocked_urlopen(*args, **kwargs):
    raise AssertionError("network must not be used during startup import")

urllib.request.urlopen = blocked_urlopen

import app

assert not any(name.startswith("tech_cartography") for name in seen), seen
assert not any(name.startswith("google.cloud") for name in seen), seen
print("startup import OK")
""".strip(),
  )
  assert result.returncode == 0, result.stderr
  assert "startup import OK" in result.stdout


def test_apptest_renders_japanese_tabs_and_keeps_saved_run_buttons(monkeypatch) -> None:
  from services_v9 import paper_openalex_retrieval
  from services_v9 import patent_bigquery_query
  from services_v9 import web_company_retrieval

  calls: list[str] = []

  def _blocked_urlopen(*args, **kwargs):
    calls.append("urlopen")
    raise AssertionError("urlopen must not be called on app render")

  def _blocked_client_factory(*args, **kwargs):
    calls.append("bigquery_client")
    raise AssertionError("BigQuery client must not be created on app render")

  def _blocked_openalex(*args, **kwargs):
    calls.append("openalex")
    raise AssertionError("OpenAlex fetch must not run on app render")

  def _blocked_tavily(*args, **kwargs):
    calls.append("tavily")
    raise AssertionError("Tavily fetch must not run on app render")

  def _blocked_grounding(*args, **kwargs):
    calls.append("grounding")
    raise AssertionError("Grounding verify must not run on app render")

  monkeypatch.setattr(urllib.request, "urlopen", _blocked_urlopen)
  monkeypatch.setattr(patent_bigquery_query, "_default_client_factory", _blocked_client_factory)
  monkeypatch.setattr(paper_openalex_retrieval, "_default_open_url", _blocked_openalex)
  monkeypatch.setattr(web_company_retrieval, "_default_tavily_json_post", _blocked_tavily)
  monkeypatch.setattr(web_company_retrieval, "_default_google_grounding_verify", _blocked_grounding)

  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()

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
