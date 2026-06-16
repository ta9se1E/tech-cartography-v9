"""Web signal source quality evaluation."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from tech_cartography.evidence.source_quality_agent import evaluate_url_quality


def evaluate_web_url_quality(url: str | None) -> dict[str, Any]:
  return evaluate_url_quality(url)


def classify_web_source_type(signal: dict[str, Any]) -> str:
  source_name = str(signal.get("source_name") or "").lower()
  source_url = str(signal.get("source_url") or signal.get("display_url") or "").lower()
  signal_type = str(signal.get("signal_type") or "").lower()
  combined = f"{source_name} {source_url} {signal_type}"

  if any(token in combined for token in ("investor", "ir.", "/ir/", "financial report", "earnings")):
    return "ir"
  if any(token in combined for token in ("press release", "press-release", "newsroom", "pr.")):
    return "press_release"
  if any(token in combined for token in (".gov", "government", "ministry", "agency")):
    return "government"
  if any(token in combined for token in (".edu", "university", "academic")):
    return "academic"
  if signal_type == "market_report" or "market report" in combined:
    return "market_report"
  if any(token in combined for token in ("blog", "medium.com", "substack")):
    return "blog"
  if any(token in combined for token in ("reuters", "bloomberg", "industry news", "trade journal")):
    return "industry_news"
  if any(token in combined for token in ("official", "corporate", "company website")) or (
    source_url and not any(host in source_url for host in ("example.com", "blog"))
  ):
    return "company_official"
  return "unknown"


def score_web_signal(signal: dict[str, Any]) -> dict[str, Any]:
  source_type = classify_web_source_type(signal)
  url_info = evaluate_web_url_quality(signal.get("display_url") or signal.get("source_url"))
  score = 0.0
  reasons: list[str] = []
  warnings: list[str] = list(signal.get("warnings", []))

  if signal.get("source_title"):
    score += 0.15
    reasons.append("source_title present")
  if signal.get("signal_date"):
    score += 0.1
    reasons.append("signal_date present")
  if url_info.get("has_url"):
    score += 0.15
    reasons.append("source_url present")
  else:
    warnings.append("Missing or weak source URL")
  if signal.get("business_signal"):
    score += 0.1
    reasons.append("business_signal present")
  if signal.get("source_name"):
    score += 0.05
    reasons.append("source_name present")

  if source_type in {"company_official", "ir", "press_release", "government"}:
    score += 0.25
    reasons.append(f"source_type={source_type}")
  elif source_type in {"industry_news", "market_report", "academic"}:
    score += 0.12
    reasons.append(f"source_type={source_type}")
  elif source_type == "blog":
    score -= 0.1
    warnings.append("Blog-like source type")
  else:
    score += 0.03

  score += url_info.get("score", 0.0) * 0.1
  if "example.com" in str(signal.get("source_url") or ""):
    score -= 0.15
    warnings.append("Template/example URL detected")

  score = max(0.0, min(1.0, score))
  if score >= 0.7:
    quality_level = "high"
    recommended_use = "cite_as_background"
  elif score >= 0.45:
    quality_level = "medium"
    recommended_use = "use_with_caution"
  elif score >= 0.2:
    quality_level = "low"
    recommended_use = "use_with_caution"
  else:
    quality_level = "unknown"
    recommended_use = "do_not_cite"

  if not url_info.get("has_url") and quality_level in {"low", "unknown"}:
    recommended_use = "do_not_cite"

  return {
    "source_type": source_type,
    "quality_level": quality_level,
    "quality_score": round(score, 3),
    "reasons": reasons,
    "warnings": warnings,
    "recommended_use": recommended_use,
  }


def evaluate_web_signal_quality(signal: dict[str, Any]) -> dict[str, Any]:
  scored = score_web_signal(signal)
  return {
    "signal_id": signal.get("signal_id"),
    "company": signal.get("company"),
    "normalized_company": signal.get("normalized_company"),
    "source_title": signal.get("source_title"),
    "display_url": signal.get("display_url") or signal.get("source_url"),
    "source_type": scored["source_type"],
    "quality_level": scored["quality_level"],
    "quality_score": scored["quality_score"],
    "reasons": scored["reasons"],
    "warnings": scored["warnings"],
    "recommended_use": scored["recommended_use"],
  }
