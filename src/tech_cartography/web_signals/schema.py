"""Web Signal schema and validation (Phase 23.0)."""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

SIGNAL_TYPES: frozenset[str] = frozenset(
  {
    "patent",
    "paper",
    "human",
    "money",
    "company",
    "local_news",
    "national_project",
    "policy",
    "market",
    "other",
  },
)

CONFIDENCE_LEVELS: frozenset[str] = frozenset(
  {"high", "medium", "low", "weak", "unknown"},
)

VERIFICATION_STATUSES: frozenset[str] = frozenset(
  {
    "verified_source",
    "needs_human_review",
    "unverified",
    "synthetic_demo",
    "rejected",
  },
)

CONFIDENCE_RANK: dict[str, int] = {
  "weak": 0,
  "low": 1,
  "unknown": 2,
  "medium": 3,
  "high": 4,
}

SYNTHETIC_DEMO_MARKER = "Synthetic demo signal"
HUMAN_MONEY_SIGNAL_TYPES: frozenset[str] = frozenset({"human", "money", "national_project"})

DEFAULT_CAVEAT = (
  "Web signals are signal candidates, not final conclusions. "
  "This is not FTO, infringement, or validity analysis."
)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


utc_now_iso = _utc_now_iso


def new_signal_id() -> str:
  return f"wsig-{uuid.uuid4().hex[:10]}"


def new_batch_id() -> str:
  return f"wsbatch-{uuid.uuid4().hex[:10]}"


def extract_source_domain(source_url: str) -> str:
  text = str(source_url or "").strip()
  if not text:
    return ""
  parsed = urlparse(text if "://" in text else f"https://{text}")
  host = (parsed.netloc or parsed.path or "").lower().strip()
  if host.startswith("www."):
    host = host[4:]
  return host


def normalize_signal_type(value: str) -> str:
  normalized = str(value or "other").strip().lower()
  if normalized in SIGNAL_TYPES:
    return normalized
  return "other"


def normalize_confidence(value: str) -> str:
  normalized = str(value or "unknown").strip().lower()
  if normalized in CONFIDENCE_LEVELS:
    return normalized
  return "unknown"


def normalize_verification_status(value: str) -> str:
  normalized = str(value or "unverified").strip().lower()
  if normalized in VERIFICATION_STATUSES:
    return normalized
  return "unverified"


def _cap_confidence(current: str, maximum: str) -> str:
  cur = normalize_confidence(current)
  max_level = normalize_confidence(maximum)
  if CONFIDENCE_RANK[cur] > CONFIDENCE_RANK[max_level]:
    return max_level
  return cur


@dataclass
class WebSignal:
  signal_id: str
  signal_type: str
  source_title: str
  source_url: str
  source_domain: str
  collected_at: str
  query: str
  raw_snippet: str
  source_date: str | None = None
  extracted_text: str | None = None
  related_company: str | None = None
  related_person: str | None = None
  related_institution: str | None = None
  related_project: str | None = None
  related_technology_terms: list[str] = field(default_factory=list)
  related_publication_numbers: list[str] = field(default_factory=list)
  related_paper_ids: list[str] = field(default_factory=list)
  confidence: str = "unknown"
  verification_status: str = "unverified"
  is_synthetic_demo: bool = False
  caveat: str = DEFAULT_CAVEAT
  next_verification_action: str = ""

  def __post_init__(self) -> None:
    self.signal_type = normalize_signal_type(self.signal_type)
    self.confidence = normalize_confidence(self.confidence)
    self.verification_status = normalize_verification_status(self.verification_status)
    if not self.source_domain:
      self.source_domain = extract_source_domain(self.source_url)


@dataclass
class WebSignalBatch:
  batch_id: str
  topic: str
  created_at: str
  query_set: list[str]
  signals: list[WebSignal]
  source_policy_version: str = "phase23.0"
  notes: str = ""


def web_signal_to_dict(signal: WebSignal) -> dict[str, Any]:
  return asdict(signal)


def web_signal_from_dict(data: dict[str, Any]) -> WebSignal:
  return WebSignal(
    signal_id=str(data.get("signal_id") or new_signal_id()),
    signal_type=str(data.get("signal_type") or "other"),
    source_title=str(data.get("source_title") or ""),
    source_url=str(data.get("source_url") or ""),
    source_domain=str(data.get("source_domain") or extract_source_domain(str(data.get("source_url") or ""))),
    source_date=data.get("source_date"),
    collected_at=str(data.get("collected_at") or _utc_now_iso()),
    query=str(data.get("query") or ""),
    raw_snippet=str(data.get("raw_snippet") or ""),
    extracted_text=data.get("extracted_text"),
    related_company=data.get("related_company"),
    related_person=data.get("related_person"),
    related_institution=data.get("related_institution"),
    related_project=data.get("related_project"),
    related_technology_terms=list(data.get("related_technology_terms") or []),
    related_publication_numbers=list(data.get("related_publication_numbers") or []),
    related_paper_ids=list(data.get("related_paper_ids") or []),
    confidence=str(data.get("confidence") or "unknown"),
    verification_status=str(data.get("verification_status") or "unverified"),
    is_synthetic_demo=bool(data.get("is_synthetic_demo")),
    caveat=str(data.get("caveat") or DEFAULT_CAVEAT),
    next_verification_action=str(data.get("next_verification_action") or ""),
  )


def web_signal_batch_to_dict(batch: WebSignalBatch) -> dict[str, Any]:
  return {
    "batch_id": batch.batch_id,
    "topic": batch.topic,
    "created_at": batch.created_at,
    "query_set": list(batch.query_set),
    "signals": [web_signal_to_dict(signal) for signal in batch.signals],
    "source_policy_version": batch.source_policy_version,
    "notes": batch.notes,
  }


def web_signal_batch_from_dict(data: dict[str, Any]) -> WebSignalBatch:
  signals = [web_signal_from_dict(row) for row in (data.get("signals") or []) if isinstance(row, dict)]
  return WebSignalBatch(
    batch_id=str(data.get("batch_id") or new_batch_id()),
    topic=str(data.get("topic") or ""),
    created_at=str(data.get("created_at") or _utc_now_iso()),
    query_set=[str(item) for item in (data.get("query_set") or [])],
    signals=signals,
    source_policy_version=str(data.get("source_policy_version") or "phase23.0"),
    notes=str(data.get("notes") or ""),
  )


def validate_web_signal(signal: WebSignal) -> list[str]:
  errors: list[str] = []
  raw_type = str(signal.signal_type or "").strip().lower()
  if raw_type not in SIGNAL_TYPES:
    errors.append(f"invalid signal_type: {signal.signal_type}")

  if signal.confidence not in CONFIDENCE_LEVELS:
    errors.append(f"invalid confidence: {signal.confidence}")

  if signal.verification_status not in VERIFICATION_STATUSES:
    errors.append(f"invalid verification_status: {signal.verification_status}")

  if signal.is_synthetic_demo:
    if signal.verification_status != "synthetic_demo":
      errors.append("is_synthetic_demo=True requires verification_status=synthetic_demo")
    if SYNTHETIC_DEMO_MARKER not in signal.caveat:
      errors.append(f"caveat must contain '{SYNTHETIC_DEMO_MARKER}' when is_synthetic_demo=True")
  else:
    if SYNTHETIC_DEMO_MARKER in signal.caveat:
      errors.append("non-synthetic signal must not contain Synthetic demo signal in caveat")
    if not str(signal.source_url or "").strip() and signal.confidence == "high":
      errors.append("source_url is required for high confidence on non-synthetic signals")
    if signal.verification_status == "verified_source" and not str(signal.source_url or "").strip():
      errors.append("verified_source requires source_url")

  if signal.signal_type == "human" and signal.verification_status != "verified_source":
    if signal.confidence == "high":
      errors.append("human signal cannot be high confidence without verified_source")

  if signal.signal_type in {"money", "national_project"}:
    if not str(signal.source_url or "").strip() and signal.confidence == "high":
      errors.append(f"{signal.signal_type} signal cannot be high confidence without source_url")

  required_fields = {
    "source_title": signal.source_title,
    "source_url": signal.source_url,
    "source_domain": signal.source_domain,
    "collected_at": signal.collected_at,
    "query": signal.query,
    "raw_snippet": signal.raw_snippet,
  }
  for name, value in required_fields.items():
    if not str(value or "").strip() and not signal.is_synthetic_demo:
      errors.append(f"missing required field: {name}")

  return errors


def build_web_signal(*, signal_type: str, **kwargs: Any) -> WebSignal:
  raw_type = str(signal_type or "").strip().lower()
  if raw_type not in SIGNAL_TYPES:
    raise ValueError(f"invalid signal_type: {signal_type}")
  signal = WebSignal(signal_type=raw_type, **kwargs)
  finalized = apply_validation_rules(signal)
  errors = validate_web_signal(finalized)
  if errors:
    raise ValueError("; ".join(errors))
  return finalized


def apply_validation_rules(signal: WebSignal) -> WebSignal:
  from tech_cartography.web_signals.synthetic_policy import ensure_synthetic_policy

  updated = ensure_synthetic_policy(signal)

  if updated.is_synthetic_demo:
    return updated

  if not str(updated.source_url or "").strip():
    updated.confidence = _cap_confidence(updated.confidence, "medium")

  if updated.signal_type == "human" and updated.verification_status != "verified_source":
    updated.confidence = _cap_confidence(updated.confidence, "medium")

  if updated.signal_type in {"money", "national_project"} and not str(updated.source_url or "").strip():
    updated.confidence = _cap_confidence(updated.confidence, "medium")

  if updated.verification_status != "verified_source":
    updated.confidence = _cap_confidence(updated.confidence, "medium")

  return updated
