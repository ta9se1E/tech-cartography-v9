"""Readiness checks for v9 OpenAlex paper retrieval."""

from __future__ import annotations

import json
import sys
import tempfile
import urllib.error
import urllib.parse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from streamlit.testing.v1 import AppTest

from services_v9.paper_openalex_retrieval import (
  build_openalex_paper_preview,
  build_openalex_search_url,
  execute_openalex_paper_retrieval,
  save_openalex_paper_retrieval_artifacts,
)
from services_v9.search_plan import build_unified_search_plan


def _profile() -> dict[str, object]:
  return {
    "theme_name": "Battery materials",
    "theme_description": "Monitor next-gen cathode and electrolyte signals.",
    "keywords": {
      "core_en": ["solid state battery", "cathode"],
      "core_ja": ["全固体電池"],
      "application_en": ["energy density", "cycle life"],
      "application_ja": ["寿命"],
      "material_process_en": ["electrolyte", "sintering"],
      "material_process_ja": ["電解質"],
      "exclude_en": ["review"],
      "exclude_ja": [],
    },
    "seed_publications": ["US20240123456A1"],
    "candidate_publications": [],
    "target_companies": ["Toyota"],
  }


def _sample_work(work_id: str, doi: str) -> dict[str, object]:
  return {
    "id": work_id,
    "display_name": f"Paper {work_id.split('/')[-1]}",
    "doi": f"https://doi.org/{doi}",
    "publication_date": "2025-01-20",
    "publication_year": 2025,
    "abstract_inverted_index": {"solid": [0], "state": [1], "battery": [2]},
    "authorships": [
      {
        "author": {"display_name": "Alice"},
        "institutions": [{"display_name": "Example University"}],
      },
    ],
    "primary_location": {
      "landing_page_url": f"https://example.org/{work_id.split('/')[-1]}",
      "source": {"display_name": "Journal of Batteries", "type": "journal"},
    },
    "cited_by_count": 9,
    "open_access": {"is_oa": True},
    "concepts": [{"display_name": "Materials science"}],
    "topics": [{"display_name": "Solid electrolytes"}],
    "language": "en",
  }


class _FakeResponse:
  def __init__(self, payload: dict[str, object]) -> None:
    self._payload = json.dumps(payload).encode("utf-8")

  def __enter__(self):
    return self

  def __exit__(self, *args):  # noqa: ANN002
    return False

  def read(self) -> bytes:
    return self._payload


def main() -> int:
  errors: list[str] = []
  plan = build_unified_search_plan(_profile())
  preview = build_openalex_paper_preview(plan, _profile(), max_results=3)
  if not preview["request"]:
    errors.append("OpenAlex preview request を生成できません")
  if preview["request"].get("provider") != "openalex":
    errors.append("provider が openalex になっていません")
  if preview["request"].get("fallback_interface", {}).get("implemented") is not False:
    errors.append("Semantic Scholar fallback interface が placeholder になっていません")

  url = build_openalex_search_url(dict(preview["request"]), cursor="abc")
  if "cursor=abc" not in url or "filter=" not in url:
    errors.append("OpenAlex URL preview に cursor/filter を反映できていません")

  payloads = {
    "*": {
      "results": [_sample_work("https://openalex.org/W1", "10.1000/test1")],
      "meta": {"next_cursor": "next-1"},
    },
    "next-1": {
      "results": [_sample_work("https://openalex.org/W2", "10.1000/test2")],
      "meta": {"next_cursor": ""},
    },
  }

  def _success_opener(request, _timeout):
    cursor = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query).get("cursor", ["*"])[0]
    return _FakeResponse(payloads[cursor])

  result = execute_openalex_paper_retrieval(dict(preview), opener=_success_opener, sleeper=lambda _s: None)
  if result["provider_status"] != "success":
    errors.append("OpenAlex staged retrieval に成功しません")
  if result["rows_retrieved"] != 2 or result["pages_fetched"] != 2:
    errors.append("cursor paging で複数ページを取得できていません")

  def _partial_opener(request, _timeout):
    cursor = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query).get("cursor", ["*"])[0]
    if cursor == "*":
      return _FakeResponse(payloads["*"])
    raise urllib.error.URLError("page 2 failed")

  partial = execute_openalex_paper_retrieval(dict(preview), opener=_partial_opener, sleeper=lambda _s: None)
  if partial["provider_status"] != "partial_success" or partial["rows_retrieved"] != 1:
    errors.append("partial success 時に部分成果物を保持できません")

  with tempfile.TemporaryDirectory() as tmp_dir_name:
    artifact_paths = save_openalex_paper_retrieval_artifacts(
      dict(preview),
      result,
      base_dir=Path(tmp_dir_name) / "v9_runs",
    )
    if not artifact_paths["staged_json"].exists() or not artifact_paths["provider_log_json"].exists():
      errors.append("OpenAlex retrieval artifact 保存に失敗しました")

  tabs_source = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")
  required_labels = [
    "OpenAlex Paper Retrieval",
    "OpenAlex論文取得を実行",
    "論文query_id",
    "provider status",
  ]
  if not all(label in tabs_source for label in required_labels):
    errors.append("情報源タブの OpenAlex UI が不足しています")

  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  button_labels = [button.label for button in at.button]
  if "OpenAlex論文取得を実行" not in button_labels:
    errors.append("Streamlit UI で OpenAlex execute ボタンを検出できません")
  if not any(select.label == "論文query_id" for select in at.selectbox):
    errors.append("Streamlit UI で 論文query_id selectbox を検出できません")

  if errors:
    for message in errors:
      print(f"[v9 paper retrieval readiness] ERROR: {message}")
    return 1
  print("[v9 paper retrieval readiness] OK: OpenAlex paper retrieval is ready.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
