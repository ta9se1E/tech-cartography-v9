"""Intelligence Delivery Hub UI — overview, report export, digest preview (Phase 24.0)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.delivery.overview import (
  DELIVERY_CAUTION,
  TabOverviewItem,
  build_tab_overviews,
  render_overview_page_md,
)
from tech_cartography.delivery.weekly_digest import PREVIEW_ONLY_NOTICE as DIGEST_PREVIEW_NOTICE
from tech_cartography.ui.easy_japanese_ui import (
  render_caution_box,
  render_info_box,
  render_markdown_preview,
  render_warning_box,
)

DEFAULT_PUB = "US-12565719-B2"
DELIVERY_RELATIVE_DIR = "outputs/delivery"
_KEY_MAX_LEN = 120


@dataclass
class DeliveryUIArtifacts:
  publication_number: str
  status: str
  delivery_dir: str
  overview_md: str | None = None
  intelligence_report_md: str | None = None
  weekly_digest_md: str | None = None
  weekly_digest_html: str | None = None
  digest_diff_md: str | None = None
  report_zip_path: Path | None = None
  intelligence_report_path: Path | None = None
  weekly_digest_md_path: Path | None = None
  weekly_digest_html_path: Path | None = None
  digest_diff_path: Path | None = None
  tab_overviews: list[TabOverviewItem] = field(default_factory=list)
  missing_artifacts: list[str] = field(default_factory=list)


def normalize_key_part(value: object) -> str:
  if value is None:
    return "none"
  text = str(value).strip()
  if not text or text.lower() in {"nan", "none", "null"}:
    return "none"
  text = re.sub(r"[/\\.\s:]+", "_", text)
  text = re.sub(r"[^a-zA-Z0-9_-]", "_", text)
  text = re.sub(r"_+", "_", text).strip("_")
  if not text:
    return "none"
  if len(text) > 48:
    text = text[:48]
  return text


def make_download_key(
  prefix: str,
  publication_number: str | None = None,
  path: Path | None = None,
  suffix: str | None = None,
) -> str:
  parts = [
    normalize_key_part(prefix),
    normalize_key_part(publication_number or "unknown"),
    normalize_key_part(path.stem if path else None),
    normalize_key_part(suffix),
  ]
  key = "_".join(part for part in parts if part and part != "none")
  if not key:
    key = "download_none"
  if len(key) > _KEY_MAX_LEN:
    key = key[:_KEY_MAX_LEN]
  return key


def collect_download_keys_for_artifacts(
  artifacts: DeliveryUIArtifacts,
  *,
  key_prefix: str = "delivery",
) -> list[str]:
  """Return unique Streamlit keys for all download buttons (for tests)."""
  pub = artifacts.publication_number
  keys = [
    make_download_key(f"{key_prefix}_dl_intelligence_report", pub, artifacts.intelligence_report_path),
    make_download_key(f"{key_prefix}_dl_weekly_digest_md", pub, artifacts.weekly_digest_md_path),
    make_download_key(f"{key_prefix}_dl_weekly_digest_html", pub, artifacts.weekly_digest_html_path),
    make_download_key(f"{key_prefix}_dl_digest_diff", pub, artifacts.digest_diff_path),
    make_download_key(f"{key_prefix}_dl_report_bundle_zip", pub, artifacts.report_zip_path),
  ]
  return keys


def _delivery_dir_for_pub(project_root: Path, publication_number: str) -> Path:
  return project_root / DELIVERY_RELATIVE_DIR


def _safe_read_text(path: Path) -> str | None:
  if not path.exists():
    return None
  try:
    return path.read_text(encoding="utf-8")
  except OSError:
    return None


def load_delivery_artifacts(
  project_root: Path | str,
  publication_number: str | None = None,
) -> DeliveryUIArtifacts:
  root = Path(project_root)
  pub_for_key = publication_number if publication_number else "unknown"
  path_pub = publication_number or DEFAULT_PUB
  ddir = _delivery_dir_for_pub(root, path_pub)

  paths = {
    "overview_page_md": ddir / "overview_page.md",
    "intelligence_report_md": ddir / f"intelligence_report_{path_pub}.md",
    "weekly_digest_md": ddir / f"weekly_digest_preview_{path_pub}.md",
    "weekly_digest_html": ddir / f"weekly_digest_preview_{path_pub}.html",
    "digest_diff_md": ddir / f"digest_diff_{path_pub}.md",
    "report_bundle_zip": ddir / f"tech_cartography_report_bundle_{path_pub}.zip",
  }

  missing = [key for key, path in paths.items() if key != "report_bundle_zip" and not path.exists()]

  available = sum(1 for key, path in paths.items() if path.exists())
  if available == 0:
    status = "missing"
  elif missing:
    status = "partial"
  else:
    status = "ready"

  zip_path = paths["report_bundle_zip"] if paths["report_bundle_zip"].exists() else None
  intel_path = paths["intelligence_report_md"] if paths["intelligence_report_md"].exists() else None
  digest_md_path = paths["weekly_digest_md"] if paths["weekly_digest_md"].exists() else None
  digest_html_path = paths["weekly_digest_html"] if paths["weekly_digest_html"].exists() else None
  diff_path = paths["digest_diff_md"] if paths["digest_diff_md"].exists() else None

  return DeliveryUIArtifacts(
    publication_number=pub_for_key,
    status=status,
    delivery_dir=str(ddir),
    overview_md=_safe_read_text(paths["overview_page_md"]),
    intelligence_report_md=_safe_read_text(paths["intelligence_report_md"]),
    weekly_digest_md=_safe_read_text(paths["weekly_digest_md"]),
    weekly_digest_html=_safe_read_text(paths["weekly_digest_html"]),
    digest_diff_md=_safe_read_text(paths["digest_diff_md"]),
    report_zip_path=zip_path,
    intelligence_report_path=intel_path,
    weekly_digest_md_path=digest_md_path,
    weekly_digest_html_path=digest_html_path,
    digest_diff_path=diff_path,
    tab_overviews=build_tab_overviews(),
    missing_artifacts=missing,
  )


def render_delivery_caution_card() -> None:
  st.markdown(
    render_caution_box(
      "Strategic Watch Brief は重点監視候補であり、最終結論ではありません。"
      "FTO、侵害、有効性判断ではありません。"
      f" {DIGEST_PREVIEW_NOTICE}"
    ),
    unsafe_allow_html=True,
  )


def render_tab_overview_section(artifacts: DeliveryUIArtifacts, *, compact: bool = False) -> None:
  st.subheader("どこを見れば何が分かるか")
  if artifacts.overview_md and not compact:
    with st.expander("まとめページ（Markdown）", expanded=False):
      st.markdown(render_markdown_preview(artifacts.overview_md, max_chars=6000))
  for tab in artifacts.tab_overviews:
    with st.expander(f"{tab.display_name} — {tab.purpose[:40]}…", expanded=compact and tab.tab_name == "start"):
      st.markdown(f"**目的**: {tab.purpose}")
      st.markdown("**分かること**:")
      for item in tab.what_you_can_learn:
        st.markdown(f"- {item}")
      st.markdown(f"**次のアクション**: {tab.typical_user_action}")
      st.caption(tab.caveat)


def render_intelligence_report_section(
  artifacts: DeliveryUIArtifacts,
  *,
  key_prefix: str = "delivery",
) -> None:
  st.subheader("Intelligence Report")
  if artifacts.intelligence_report_md:
    with st.expander("Markdown Preview", expanded=True):
      st.markdown(render_markdown_preview(artifacts.intelligence_report_md, max_chars=8000))
    report_key = make_download_key(
      f"{key_prefix}_dl_intelligence_report",
      artifacts.publication_number,
      artifacts.intelligence_report_path,
    )
    file_pub = artifacts.publication_number if artifacts.publication_number != "unknown" else DEFAULT_PUB
    st.download_button(
      label="Download Intelligence Report (.md)",
      data=artifacts.intelligence_report_md,
      file_name=f"intelligence_report_{file_pub}.md",
      mime="text/markdown",
      key=report_key,
    )
  else:
    st.info(
      "Intelligence Report がまだありません。"
      " `python scripts/build_delivery_package.py` を実行してください。"
    )


def render_weekly_digest_preview_section(
  artifacts: DeliveryUIArtifacts,
  *,
  key_prefix: str = "delivery",
) -> None:
  st.subheader("Weekly Digest Preview")
  st.markdown(
    render_warning_box(f"<strong>{DIGEST_PREVIEW_NOTICE}</strong>"),
    unsafe_allow_html=True,
  )
  file_pub = artifacts.publication_number if artifacts.publication_number != "unknown" else DEFAULT_PUB

  if artifacts.digest_diff_md:
    with st.expander("What changed this week (Diff)", expanded=True):
      st.markdown(render_markdown_preview(artifacts.digest_diff_md, max_chars=4000))
    diff_key = make_download_key(
      f"{key_prefix}_dl_digest_diff",
      artifacts.publication_number,
      artifacts.digest_diff_path,
    )
    st.download_button(
      label="Download digest_diff.md",
      data=artifacts.digest_diff_md,
      file_name=f"digest_diff_{file_pub}.md",
      mime="text/markdown",
      key=diff_key,
    )

  if artifacts.weekly_digest_md:
    with st.expander("Digest Markdown Preview"):
      st.markdown(render_markdown_preview(artifacts.weekly_digest_md, max_chars=6000))
    digest_md_key = make_download_key(
      f"{key_prefix}_dl_weekly_digest_md",
      artifacts.publication_number,
      artifacts.weekly_digest_md_path,
    )
    st.download_button(
      label="Download weekly_digest_preview.md",
      data=artifacts.weekly_digest_md,
      file_name=f"weekly_digest_preview_{file_pub}.md",
      mime="text/markdown",
      key=digest_md_key,
    )

  if artifacts.weekly_digest_html:
    digest_html_key = make_download_key(
      f"{key_prefix}_dl_weekly_digest_html",
      artifacts.publication_number,
      artifacts.weekly_digest_html_path,
    )
    st.download_button(
      label="Download weekly_digest_preview.html",
      data=artifacts.weekly_digest_html,
      file_name=f"weekly_digest_preview_{file_pub}.html",
      mime="text/html",
      key=digest_html_key,
    )
  elif not artifacts.weekly_digest_md:
    st.info("Weekly Digest Preview がまだありません。初回は initial snapshot として生成されます。")


def render_report_bundle_zip_section(
  artifacts: DeliveryUIArtifacts,
  *,
  key_prefix: str = "delivery",
) -> None:
  st.subheader("Report Bundle Zip")
  if artifacts.report_zip_path and artifacts.report_zip_path.exists():
    zip_bytes = artifacts.report_zip_path.read_bytes()
    bundle_key = make_download_key(
      f"{key_prefix}_dl_report_bundle_zip",
      artifacts.publication_number,
      artifacts.report_zip_path,
    )
    st.download_button(
      label="Download tech_cartography_report_bundle.zip",
      data=zip_bytes,
      file_name=artifacts.report_zip_path.name,
      mime="application/zip",
      key=bundle_key,
    )
  else:
    st.info("ZIP bundle がまだありません。`--include-zip` で生成してください。")


def render_delivery_section(
  artifacts: DeliveryUIArtifacts,
  *,
  show_overview: bool = True,
  compact_overview: bool = False,
  key_prefix: str = "delivery",
) -> None:
  st.markdown("## Intelligence Delivery / Export")

  if artifacts.status == "missing":
    st.warning(
      "Delivery 成果物が見つかりません。"
      " 先に `python scripts/build_delivery_package.py` を実行してください。"
      " 下記はタブ説明のみ表示します。"
    )

  render_delivery_caution_card()

  if show_overview:
    render_tab_overview_section(artifacts, compact=compact_overview)

  st.divider()
  render_intelligence_report_section(artifacts, key_prefix=key_prefix)
  st.divider()
  render_weekly_digest_preview_section(artifacts, key_prefix=key_prefix)
  st.divider()
  render_report_bundle_zip_section(artifacts, key_prefix=key_prefix)

  st.markdown(
    render_info_box(DELIVERY_CAUTION),
    unsafe_allow_html=True,
  )
