"""Search axis preview builders for the bilingual v9.2 watch profile."""

from __future__ import annotations

from .watch_profile_schema import migrate_watch_profile


def _join_terms(terms: list[str]) -> str:
  return " OR ".join(terms) if terms else "なし"


def build_patent_query_preview(profile: dict) -> str:
  migrated = migrate_watch_profile(profile)
  keywords = migrated["keywords"]
  lines = [
    "これは検索実行ではなくPreviewです。",
    "検索対象:",
    f"- コア語: {_join_terms(keywords['core_en'] + keywords['core_ja'])}",
    f"- 材料・プロセス語: {_join_terms(keywords['material_process_en'] + keywords['material_process_ja'])}",
    f"- Seed公報: {', '.join(migrated['seed_publications']) if migrated['seed_publications'] else 'なし'}",
    "除外:",
    f"- {_join_terms(keywords['exclude_en'] + keywords['exclude_ja'])}",
  ]
  return "\n".join(lines)


def build_paper_query_preview(profile: dict) -> str:
  migrated = migrate_watch_profile(profile)
  keywords = migrated["keywords"]
  lines = [
    "これは検索実行ではなくPreviewです。",
    "検索対象:",
    f"- コア語: {_join_terms(keywords['core_en'] + keywords['core_ja'])}",
    f"- 用途語: {_join_terms(keywords['application_en'] + keywords['application_ja'])}",
    f"- 材料・プロセス語: {_join_terms(keywords['material_process_en'] + keywords['material_process_ja'])}",
    "除外:",
    f"- {_join_terms(keywords['exclude_en'] + keywords['exclude_ja'])}",
  ]
  return "\n".join(lines)


def build_web_query_preview(profile: dict) -> str:
  migrated = migrate_watch_profile(profile)
  keywords = migrated["keywords"]
  lines = [
    "これは検索実行ではなくPreviewです。",
    f"監視テーマ: {migrated['theme_name'] or '未設定'}",
    f"注目企業: {', '.join(migrated['target_companies']) if migrated['target_companies'] else 'なし'}",
    f"用途語: {_join_terms(keywords['application_en'] + keywords['application_ja'])}",
    f"材料・プロセス語: {_join_terms(keywords['material_process_en'] + keywords['material_process_ja'])}",
  ]
  return "\n".join(lines)


def build_company_query_preview(profile: dict) -> str:
  migrated = migrate_watch_profile(profile)
  keywords = migrated["keywords"]
  lines = [
    "これは検索実行ではなくPreviewです。",
    f"監視テーマ: {migrated['theme_name'] or '未設定'}",
    f"対象企業: {', '.join(migrated['target_companies']) if migrated['target_companies'] else 'なし'}",
    f"用途語: {_join_terms(keywords['application_en'] + keywords['application_ja'])}",
    f"材料・プロセス語: {_join_terms(keywords['material_process_en'] + keywords['material_process_ja'])}",
  ]
  return "\n".join(lines)


def build_query_preview_bundle(profile: dict) -> dict[str, str]:
  return {
    "patent": build_patent_query_preview(profile),
    "paper": build_paper_query_preview(profile),
    "web": build_web_query_preview(profile),
    "company": build_company_query_preview(profile),
  }
