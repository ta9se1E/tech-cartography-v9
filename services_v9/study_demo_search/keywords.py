"""Local keyword suggestions for study demo search."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Mapping, Sequence

_WORD = re.compile(r"[A-Za-z0-9\u3040-\u30ff\u3400-\u9fff]{2,}")


def build_keyword_suggestions(signals: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
  corpus: list[str] = []
  cpc: Counter[str] = Counter()
  topics: Counter[str] = Counter()
  companies: Counter[str] = Counter()
  web_terms: Counter[str] = Counter()
  for signal in signals:
    text = " ".join(
      [
        str(signal.get("title", "") or ""),
        str(signal.get("summary", "") or ""),
      ]
    )
    corpus.extend(_WORD.findall(text.lower()))
    meta = dict(signal.get("metadata", {}) or {})
    for code in list(meta.get("cpc_codes", []) or []):
      cpc[str(code)] += 1
    for topic in list(meta.get("topics", []) or []):
      topics[str(topic)] += 1
    org = str(signal.get("organization", "") or "").strip()
    if org:
      companies[org] += 1
    if str(signal.get("source_type", "")) == "web_company":
      for token in _WORD.findall(text):
        web_terms[token] += 1

  freq = Counter(corpus)
  return {
    "add_keywords": [item for item, _ in freq.most_common(15)],
    "exclude_terms": [],
    "company_candidates": [item for item, _ in companies.most_common(10)],
    "cpc_ipc_candidates": [item for item, _ in cpc.most_common(10)],
    "paper_topic_candidates": [item for item, _ in topics.most_common(10)],
    "web_activity_terms": [item for item, _ in web_terms.most_common(10)],
    "notes": "Suggestions are local-only; auto-apply is disabled.",
  }
