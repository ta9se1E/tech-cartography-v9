"""Web Signal Foundation — schema, quality, storage, Tavily adapter (Phase 23.0 / 23.1)."""

from tech_cartography.web_signals.schema import (
  SIGNAL_TYPES,
  CONFIDENCE_LEVELS,
  VERIFICATION_STATUSES,
  DISCLOSURE_TYPES,
  SOURCE_KINDS,
  WebSignal,
  WebSignalBatch,
  apply_validation_rules,
  new_batch_id,
  new_signal_id,
  validate_web_signal,
  web_signal_from_dict,
  web_signal_to_dict,
)
from tech_cartography.web_signals.source_quality import classify_source_quality
from tech_cartography.web_signals.synthetic_policy import (
  SYNTHETIC_DEMO_MARKER,
  ensure_synthetic_policy,
)
from tech_cartography.web_signals.query_templates import WebSignalQuery, build_web_signal_queries
from tech_cartography.web_signals.store import (
  SOURCE_POLICY_VERSION,
  load_web_signal_batch,
  render_web_signal_summary_md,
  save_tavily_web_signal_run,
  save_web_signal_batch,
  web_signals_to_dataframe,
)
from tech_cartography.web_signals.tavily_adapter import (
  build_tavily_extract_payload,
  build_tavily_search_payload,
  get_tavily_api_key,
  run_tavily_extract,
  run_tavily_search,
  tavily_extract_results_to_web_signals,
  tavily_search_results_to_web_signals,
)

__all__ = [
  "SIGNAL_TYPES",
  "CONFIDENCE_LEVELS",
  "VERIFICATION_STATUSES",
  "DISCLOSURE_TYPES",
  "SOURCE_KINDS",
  "WebSignal",
  "WebSignalBatch",
  "apply_validation_rules",
  "new_batch_id",
  "new_signal_id",
  "validate_web_signal",
  "web_signal_from_dict",
  "web_signal_to_dict",
  "classify_source_quality",
  "SYNTHETIC_DEMO_MARKER",
  "ensure_synthetic_policy",
  "WebSignalQuery",
  "build_web_signal_queries",
  "SOURCE_POLICY_VERSION",
  "load_web_signal_batch",
  "render_web_signal_summary_md",
  "save_tavily_web_signal_run",
  "save_web_signal_batch",
  "web_signals_to_dataframe",
  "build_tavily_extract_payload",
  "build_tavily_search_payload",
  "get_tavily_api_key",
  "run_tavily_extract",
  "run_tavily_search",
  "tavily_extract_results_to_web_signals",
  "tavily_search_results_to_web_signals",
]
