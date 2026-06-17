"""Manual fulltext input schema — paste claims/description from Google Patents (no OCR yet)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MANUAL_INPUT_ROOT = "outputs/manual_fulltext_inputs"


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_filename(publication_number: str) -> str:
  return re.sub(r"[^\w\-]+", "_", str(publication_number or "unknown").strip())


@dataclass
class ManualFulltextInput:
  publication_number: str
  source_url: str = ""
  claims_text: str = ""
  description_text: str = ""
  source_note: str = ""
  entered_by: str = ""
  created_at: str = ""
  warnings: list[str] = field(default_factory=list)


def validate_manual_fulltext_input(data: ManualFulltextInput | dict[str, Any]) -> list[str]:
  row = data if isinstance(data, dict) else asdict(data)
  warnings: list[str] = []
  if not str(row.get("publication_number") or "").strip():
    warnings.append("publication_number is required")
  claims = str(row.get("claims_text") or "").strip()
  description = str(row.get("description_text") or "").strip()
  if not claims and not description:
    warnings.append("claims_text and description_text are both empty")
  return warnings


def manual_fulltext_input_to_dict(entry: ManualFulltextInput) -> dict[str, Any]:
  return asdict(entry)


def load_manual_fulltext_input(
  publication_number: str,
  *,
  root: str | Path = DEFAULT_MANUAL_INPUT_ROOT,
) -> dict[str, Any] | None:
  path = Path(root) / f"{_safe_filename(publication_number)}.json"
  if not path.exists():
    return None
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None
  except json.JSONDecodeError:
    return None


def save_manual_fulltext_input(
  entry: ManualFulltextInput | dict[str, Any],
  *,
  root: str | Path = DEFAULT_MANUAL_INPUT_ROOT,
) -> dict[str, Any]:
  if isinstance(entry, dict):
    row = dict(entry)
  else:
    row = manual_fulltext_input_to_dict(entry)
  if not row.get("created_at"):
    row["created_at"] = _utc_now_iso()
  row["warnings"] = validate_manual_fulltext_input(row)
  out_dir = Path(root)
  out_dir.mkdir(parents=True, exist_ok=True)
  pub = str(row.get("publication_number") or "unknown")
  path = out_dir / f"{_safe_filename(pub)}.json"
  path.write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
  return {"path": str(path), "publication_number": pub, "warnings": row["warnings"]}
