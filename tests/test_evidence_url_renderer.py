"""Tests for paper URL rendering (Phase 24.5B)."""

from __future__ import annotations

from tech_cartography.ui.evidence_map_demo import (
  prepare_claim_paper_links_display_df,
  prepare_selected_papers_display_df,
)
from tech_cartography.ui.label_renderer import (
  format_paper_link_markdown,
  normalize_doi,
  resolve_paper_url,
)
import pandas as pd


def test_doi_generates_https_doi_org_link() -> None:
  url = resolve_paper_url({"doi": "10.1016/j.pmatsci.2019.100575"})
  assert url == "https://doi.org/10.1016/j.pmatsci.2019.100575"


def test_doi_prefix_stripped() -> None:
  assert normalize_doi("https://doi.org/10.1234/example") == "10.1234/example"
  url = resolve_paper_url({"doi": "doi:10.1234/example"})
  assert url.startswith("https://doi.org/10.1234")


def test_openalex_id_fallback() -> None:
  url = resolve_paper_url({"openalex_id": "https://openalex.org/W2949920894"})
  assert "openalex.org" in url


def test_landing_page_url_preferred_when_no_doi() -> None:
  url = resolve_paper_url(
    {"landing_page_url": "https://example.org/paper", "source_url": "https://other.org"},
  )
  assert url == "https://example.org/paper"


def test_format_paper_link_markdown_short_label() -> None:
  md = format_paper_link_markdown("https://doi.org/10.1/x")
  assert md == "[論文を開く](https://doi.org/10.1/x)"
  assert "https://doi.org/10.1/x" not in md.replace("[論文を開く](https://doi.org/10.1/x)", "")


def test_selected_papers_display_includes_paper_link_column() -> None:
  df = pd.DataFrame([{"title": "Paper", "doi": "10.1234/example"}])
  display = prepare_selected_papers_display_df(df)
  assert "論文を開く" in display.columns
  assert "[論文を開く]" in display.iloc[0]["論文を開く"]
  assert "https://doi.org/10.1234/example" in display.iloc[0]["論文を開く"]


def test_claim_links_display_includes_paper_link_column() -> None:
  df = pd.DataFrame(
    [{"claim_element": "CE-1", "paper_title": "Paper A", "paper_doi": "10.1/x"}],
  )
  display = prepare_claim_paper_links_display_df(df)
  assert "論文を開く" in display.columns
  assert "doi.org" in display.iloc[0]["論文を開く"]
