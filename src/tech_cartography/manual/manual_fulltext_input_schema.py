"""Manual fulltext input schema — Google Patents paste route (Phase 18B)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MANUAL_INPUT_ROOT = "outputs/manual_fulltext_inputs"

VALID_INPUT_SCOPES = frozenset({"claims_only", "description_only", "claims_and_description"})
VALID_INPUT_ROUTES = frozenset({"manual_google_patents", "manual_pdf", "manual_user_paste"})
VALIDATION_STATUSES = frozenset(
  {
    "valid_claims_only",
    "valid_claims_and_description",
    "missing_claims",
    "empty_input",
    "invalid_publication_number",
  },
)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_filename(publication_number: str) -> str:
  safe = re.sub(r"[^\w\-]+", "_", str(publication_number or "unknown").strip())
  return f"{safe}.json"


def normalize_manual_claims_text(text: str) -> str:
  raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
  lines = [line.rstrip() for line in raw.split("\n")]
  return "\n".join(lines).strip()


def normalize_manual_description_text(text: str) -> str:
  return normalize_manual_claims_text(text)


def _has_us_publication_number(publication_number: str) -> bool:
  compact = re.sub(r"[\s\-]+", "", str(publication_number or "").upper())
  return compact.startswith("US") and len(compact) > 2


@dataclass
class ManualFulltextInput:
  publication_number: str
  source_url: str | None = None
  claims_text: str | None = None
  description_text: str | None = None
  source_note: str | None = None
  entered_by: str | None = None
  created_at: str = ""
  input_scope: str = "claims_only"
  input_route: str = "manual_user_paste"
  validation_status: str = ""
  warnings: list[str] = field(default_factory=list)


def manual_fulltext_input_from_dict(data: dict[str, Any]) -> ManualFulltextInput:
  return ManualFulltextInput(
    publication_number=str(data.get("publication_number") or ""),
    source_url=data.get("source_url"),
    claims_text=data.get("claims_text"),
    description_text=data.get("description_text"),
    source_note=data.get("source_note"),
    entered_by=data.get("entered_by"),
    created_at=str(data.get("created_at") or ""),
    input_scope=str(data.get("input_scope") or "claims_only"),
    input_route=str(data.get("input_route") or "manual_user_paste"),
    validation_status=str(data.get("validation_status") or ""),
    warnings=list(data.get("warnings") or []),
  )


def manual_fulltext_input_to_dict(entry: ManualFulltextInput) -> dict[str, Any]:
  return asdict(entry)


def validate_manual_fulltext_input(data: ManualFulltextInput | dict[str, Any]) -> dict[str, Any]:
  row = manual_fulltext_input_to_dict(data) if isinstance(data, ManualFulltextInput) else dict(data)
  warnings: list[str] = []
  pub = str(row.get("publication_number") or "").strip()
  claims = normalize_manual_claims_text(str(row.get("claims_text") or ""))
  description = normalize_manual_description_text(str(row.get("description_text") or ""))

  if not pub:
    return {
      "validation_status": "invalid_publication_number",
      "warnings": ["publication_number is required"],
      "claims_present": False,
      "description_present": False,
      "input_scope": row.get("input_scope", "claims_only"),
    }

  if not _has_us_publication_number(pub) and not re.match(r"^[A-Z]{2}", pub.replace("-", "")):
    warnings.append("publication_number format may be invalid")

  if not claims and not description:
    return {
      "validation_status": "empty_input",
      "warnings": ["claims_text and description_text are both empty"],
      "claims_present": False,
      "description_present": False,
      "input_scope": row.get("input_scope", "claims_only"),
    }

  if not claims:
    status = "missing_claims"
    warnings.append("claims_text is empty; claim element extraction will not run")
  elif claims and description:
    status = "valid_claims_and_description"
  else:
    status = "valid_claims_only"

  input_scope = str(row.get("input_scope") or "claims_only")
  if status == "valid_claims_and_description":
    input_scope = "claims_and_description"
  elif status == "valid_claims_only":
    input_scope = "claims_only"
  elif description and not claims:
    input_scope = "description_only"

  return {
    "validation_status": status,
    "warnings": warnings,
    "claims_present": bool(claims),
    "description_present": bool(description),
    "input_scope": input_scope,
  }


def _resolve_input_path(publication_number: str, input_dir: str | Path) -> Path:
  root = Path(input_dir)
  candidates = [
    root / f"{publication_number.strip()}.json",
    root / _json_filename(publication_number),
  ]
  for path in candidates:
    if path.exists():
      return path
  return candidates[0]


def load_manual_fulltext_input(
  publication_number: str,
  input_dir: str | Path = DEFAULT_MANUAL_INPUT_ROOT,
) -> ManualFulltextInput | None:
  path = _resolve_input_path(publication_number, input_dir)
  if not path.exists():
    return None
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
      return None
    return manual_fulltext_input_from_dict(data)
  except json.JSONDecodeError:
    return None


def save_manual_fulltext_input(
  entry: ManualFulltextInput,
  output_dir: str | Path = DEFAULT_MANUAL_INPUT_ROOT,
) -> str:
  validation = validate_manual_fulltext_input(entry)
  row = manual_fulltext_input_to_dict(entry)
  row["claims_text"] = normalize_manual_claims_text(str(row.get("claims_text") or "")) or None
  row["description_text"] = normalize_manual_description_text(str(row.get("description_text") or "")) or None
  row["validation_status"] = validation["validation_status"]
  row["input_scope"] = validation.get("input_scope", row.get("input_scope", "claims_only"))
  row["warnings"] = list(validation.get("warnings") or [])
  if not row.get("created_at"):
    row["created_at"] = _utc_now_iso()

  out_dir = Path(output_dir)
  out_dir.mkdir(parents=True, exist_ok=True)
  path = out_dir / _json_filename(str(row.get("publication_number") or "unknown"))
  path.write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
  return str(path)
