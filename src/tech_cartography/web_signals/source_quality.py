"""Source quality classification for Web Signals (Phase 23.0)."""

from __future__ import annotations

from urllib.parse import urlparse

from tech_cartography.web_signals.schema import extract_source_domain

HIGH_QUALITY_DOMAINS: frozenset[str] = frozenset(
  {
    "jst.go.jp",
    "nedo.go.jp",
    "meti.go.jp",
    "mext.go.jp",
    "grants.jst.go.jp",
    "kaken.nii.ac.jp",
    "amed.go.jp",
  },
)

PUBLIC_FUNDING_DOMAINS: frozenset[str] = frozenset(
  {
    "jst.go.jp",
    "nedo.go.jp",
    "grants.jst.go.jp",
    "kaken.nii.ac.jp",
    "amed.go.jp",
  },
)

GOVERNMENT_DOMAINS: frozenset[str] = frozenset(
  {
    "meti.go.jp",
    "mext.go.jp",
    "go.jp",
  },
)

LOW_QUALITY_HINTS: tuple[str, ...] = (
  "linkedin.com",
  "twitter.com",
  "x.com",
  "facebook.com",
  "instagram.com",
  "tiktok.com",
  "reddit.com",
  "medium.com",
  "note.com",
  "qiita.com",
  "wantedly.com",
  "indeed.com",
  "rikunabi.com",
  "mynavi.jp",
  "blogspot.",
  "wordpress.com",
)

INDUSTRY_MEDIA_HINTS: tuple[str, ...] = (
  "nikkei.com",
  "chemicaldaily.co.jp",
  "plasticsnews.com",
  "compositesworld.com",
)

LOCAL_NEWS_HINTS: tuple[str, ...] = (
  "local",
  "pref.",
  "city.",
  "news.co.jp",
  "shimbun",
)


def _match_domain(domain: str, suffix: str) -> bool:
  return domain == suffix or domain.endswith(f".{suffix}")


def classify_source_quality(source_url: str) -> dict[str, str]:
  domain = extract_source_domain(source_url)
  if not domain:
    return {
      "source_domain": "",
      "source_quality": "unknown",
      "source_category": "unknown",
      "caveat": "source_url is missing; treat as unverified signal candidate.",
    }

  if domain in HIGH_QUALITY_DOMAINS or any(_match_domain(domain, item) for item in HIGH_QUALITY_DOMAINS):
    category = "public_funding" if domain in PUBLIC_FUNDING_DOMAINS else "government"
    return {
      "source_domain": domain,
      "source_quality": "high",
      "source_category": category,
      "caveat": "Public or government source domain; still requires human review for linkage.",
    }

  if domain.endswith(".go.jp") or _match_domain(domain, "go.jp"):
    return {
      "source_domain": domain,
      "source_quality": "high",
      "source_category": "government",
      "caveat": "Government domain; verify page relevance before use.",
    }

  if domain.endswith(".ac.jp") or domain.endswith(".edu"):
    return {
      "source_domain": domain,
      "source_quality": "medium_high",
      "source_category": "university",
      "caveat": "University official domain candidate; confirm publication context.",
    }

  if domain.endswith(".co.jp") or domain.endswith(".com") or domain.endswith(".corp"):
    if any(hint in domain for hint in LOW_QUALITY_HINTS):
      pass
    else:
      return {
        "source_domain": domain,
        "source_quality": "medium_high",
        "source_category": "company_official",
        "caveat": "Company domain candidate; verify official press release or IR page.",
      }

  if any(hint in domain for hint in LOW_QUALITY_HINTS):
    category = "job_board" if any(j in domain for j in ("indeed", "rikunabi", "mynavi", "wantedly")) else "social"
    if "blog" in domain or "medium.com" in domain or "note.com" in domain:
      category = "blog"
    return {
      "source_domain": domain,
      "source_quality": "low",
      "source_category": category,
      "caveat": "Low-trust domain; use only as weak signal candidate.",
    }

  if any(hint in domain for hint in LOCAL_NEWS_HINTS):
    return {
      "source_domain": domain,
      "source_quality": "medium",
      "source_category": "news",
      "caveat": "Local or regional news candidate; verify date and entity linkage.",
    }

  if any(hint in domain for hint in INDUSTRY_MEDIA_HINTS):
    return {
      "source_domain": domain,
      "source_quality": "medium",
      "source_category": "news",
      "caveat": "Industry media candidate; not a final business conclusion.",
    }

  return {
    "source_domain": domain,
    "source_quality": "unknown",
    "source_category": "unknown",
    "caveat": "Unknown domain quality; manual review required.",
  }
