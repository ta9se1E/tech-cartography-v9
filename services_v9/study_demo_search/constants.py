"""Constants for study demo three-source search."""

from __future__ import annotations

SEARCH_RUN_PREFIX = "search_runs/"
SEARCH_CONTROL_PREFIX = "search_control/"
SEARCH_LOCK_OBJECT = "search_control/search.lock"
SEARCH_USAGE_OBJECT = "search_control/search_usage.json"
MAX_FIELD_LENGTH = 300
DEFAULT_PATENT_DISPLAY_LIMIT = 50
DEFAULT_PAPER_DISPLAY_LIMIT = 50
DEFAULT_WEB_MAX_RESULTS = 10
STUDY_DEMO_BQ_MAX_BYTES_BILLED_DEFAULT = 2_199_023_255_552  # 2 TiB
ROLLBACK_REVISION = "tech-cartography-v9-study-demo-00001-b48"

PRODUCTION_SECRET_DENYLIST = frozenset(
  {
    "tech-cartography-smtp-password",
    "tech-cartography-tavily-api-key",
    "tech-cartography-v9-study-demo-password",
  }
)

STUDY_DEMO_OPENALEX_SECRET = "tech-cartography-v9-study-demo-openalex-api-key"
STUDY_DEMO_TAVILY_SECRET = "tech-cartography-v9-study-demo-tavily-api-key"

COMMON_SIGNAL_FIELDS = (
  "signal_id",
  "source_type",
  "source_id",
  "title",
  "summary",
  "url",
  "published_at",
  "organization",
  "country",
  "language",
  "technology_terms",
  "material_terms",
  "process_terms",
  "property_terms",
  "relevance_score",
  "source_score",
  "source_quality",
  "query_provenance",
  "retrieved_at",
  "search_run_id",
  "family_id",
  "metadata",
)

FORBIDDEN_INPUT_PATTERNS = (
  "select ",
  "insert ",
  "update ",
  "delete ",
  "drop ",
  "create ",
  "alter ",
  "merge ",
  "truncate ",
  "export ",
  ";",
  "--",
  "/*",
  "*/",
  "|",
  "&&",
  "||",
  "`",
  "$( ",
)

WEB_ACTIVITY_CATEGORIES = (
  "技術・研究",
  "投資・生産",
  "提携・プロジェクト",
  "事業化",
  "組織・人材",
  "制度・規制",
  "その他",
)
