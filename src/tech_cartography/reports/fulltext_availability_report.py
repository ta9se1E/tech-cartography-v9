"""User-facing fulltext availability diagnostic report (no monetary amounts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_COST_KEYS = ("usd", "cost", "price", "budget", "estimated_bytes")


def _scrub_public(data: dict[str, Any]) -> dict[str, Any]:
  clean: dict[str, Any] = {}
  for key, value in data.items():
    if any(token in key.lower() for token in _COST_KEYS):
      continue
    if isinstance(value, dict):
      clean[key] = _scrub_public(value)
    elif isinstance(value, list):
      clean[key] = [
        _scrub_public(item) if isinstance(item, dict) else item for item in value
      ]
    else:
      clean[key] = value
  return clean


def render_fulltext_availability_markdown(result: dict[str, Any]) -> str:
  pub = result.get("publication_number", "")
  lines = [
    "# Fulltext Availability Probe",
    "",
    "## 対象",
    "",
    str(pub),
    "",
    "## 確認した番号形式",
    "",
  ]
  for variant in result.get("variants_checked") or []:
    lines.append(f"- {variant}")

  lines.extend(
    [
      "",
      "## 結果",
      "",
      f"- 状態: {result.get('probe_status', '')}",
      f"- 一致した番号: {result.get('matched_variant') or '（なし）'}",
      f"- 公報行: {'あり' if result.get('has_publication_row') else 'なし'}",
      f"- 請求項: {'あり' if result.get('has_claims') else 'なし'}",
      f"- 明細書: {'あり' if result.get('has_description') else 'なし'}",
      "",
      result.get("user_status_japanese") or "",
      "",
      "## 原因仮説（内部メモ要約）",
      "",
    ],
  )
  for note in result.get("internal_notes") or []:
    lines.append(f"- {note}")

  lines.extend(["", "## 次アクション", "", result.get("next_action_japanese") or ""])
  actions = []
  status = str(result.get("probe_status") or "")
  if status == "found_claims":
    actions.append("BigQueryでclaims取得に進む")
  else:
    actions.append("Google Patents / manual routeへ")
  actions.append("番号形式を確認")
  if not result.get("has_claims"):
    actions.append("A1公開公報候補をmetadataから確認（無根拠の推定はしない）")
  for action in actions:
    lines.append(f"- {action}")

  urls = result.get("google_patents_urls") or []
  if urls:
    lines.extend(["", "## Google Patents", ""])
    for url in urls[:5]:
      lines.append(f"- {url}")

  lines.append("")
  lines.append("※ 金額・課金情報はこのレポートに含めません。")
  return "\n".join(lines)


def save_fulltext_availability_report(
  result: dict[str, Any],
  output_dir: str | Path,
) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  public = _scrub_public(result)
  json_path = out / "fulltext_availability_probe.json"
  md_path = out / "fulltext_availability_probe.md"
  json_path.write_text(json.dumps(public, indent=2, ensure_ascii=False), encoding="utf-8")
  md_path.write_text(render_fulltext_availability_markdown(public), encoding="utf-8")
  return {
    "fulltext_availability_probe_json": str(json_path),
    "fulltext_availability_probe_md": str(md_path),
  }
