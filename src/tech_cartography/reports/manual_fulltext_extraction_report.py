"""Manual fulltext extraction status report (no monetary amounts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def render_manual_fulltext_extraction_markdown(
  records: list[dict[str, Any]],
  claim_element_result: dict[str, Any] | None = None,
) -> str:
  claim_result = claim_element_result or {}
  lines = ["# Manual Fulltext Extraction Status", ""]
  manual_records = [
    r for r in records
    if str(r.get("retrieval_status") or "") in {"manual_claims_loaded", "manual_fulltext_loaded"}
    or r.get("manual_route")
  ]
  if not manual_records:
    lines.extend(["手動入力ルートの対象はまだありません。", ""])
    return "\n".join(lines)

  for record in manual_records:
    pub = record.get("publication_number", "")
    lines.extend(
      [
        "## 対象",
        "",
        str(pub),
        "",
        "## 入力ルート",
        "",
        str(record.get("input_route") or record.get("claims_source") or "manual_user_paste"),
        "",
        "## 取得できた情報",
        "",
        f"- claims: {'yes' if record.get('claims_length', 0) else 'no'}",
        f"- description: {'yes' if record.get('description_length', 0) else 'no'}",
        "",
      ],
    )

  lines.extend(["## Claim Element抽出", ""])
  element_types: dict[str, int] = {}
  for element in claim_result.get("elements", []):
    row = element.to_dict() if hasattr(element, "to_dict") else element
    etype = str(row.get("element_type") or "unknown")
    element_types[etype] = element_types.get(etype, 0) + 1
  if element_types:
    for etype, count in sorted(element_types.items()):
      lines.append(f"- {etype}: {count}")
  else:
    lines.append("- （まだ抽出されていません）")

  lines.extend(
    [
      "",
      "## 注意",
      "",
      "明細書が未入力の場合、実施例・測定条件の裏取りは限定的です。",
      "論文候補は証明ではありません。専門家レビューが必要です。",
      "",
      "※ 金額・課金情報は表示していません。",
    ],
  )
  return "\n".join(lines)


def save_manual_fulltext_extraction_artifacts(
  records: list[dict[str, Any]],
  claim_element_result: dict[str, Any],
  output_dir: str | Path,
) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  manual_pubs = {
    str(r.get("publication_number") or "")
    for r in records
    if str(r.get("retrieval_status") or "") in {"manual_claims_loaded", "manual_fulltext_loaded"}
  }
  element_rows = []
  for element in claim_element_result.get("elements", []):
    row = element.to_dict() if hasattr(element, "to_dict") else dict(element)
    if str(row.get("publication_number") or "") in manual_pubs:
      element_rows.append(row)

  from tech_cartography.reports.project_export import save_records_csv

  json_path = out / "claim_elements_from_manual_fulltext.json"
  csv_path = out / "claim_elements_from_manual_fulltext.csv"
  md_path = out / "manual_fulltext_extraction_status.md"

  json_path.write_text(json.dumps(element_rows, indent=2, ensure_ascii=False), encoding="utf-8")
  save_records_csv(element_rows, csv_path)
  md_path.write_text(
    render_manual_fulltext_extraction_markdown(records, claim_element_result),
    encoding="utf-8",
  )
  return {
    "claim_elements_from_manual_fulltext_json": str(json_path),
    "claim_elements_from_manual_fulltext_csv": str(csv_path),
    "manual_fulltext_extraction_status_md": str(md_path),
  }
