"""Company name normalization and matching for carbon fiber domain."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def build_company_aliases() -> dict[str, list[str]]:
  return {
    "TORAY": ["TORAY INDUSTRIES", "TORAY INDUSTRIES INC", "東レ", "東レ株式会社"],
    "TEIJIN": ["TEIJIN LIMITED", "TEIJIN LTD", "帝人", "帝人株式会社"],
    "MITSUBISHI CHEMICAL": [
      "MITSUBISHI CHEM",
      "MITSUBISHI CHEMICAL GROUP",
      "三菱ケミカル",
      "三菱ケミカルグループ",
    ],
    "HYOSUNG": ["HYOSUNG ADVANCED MATERIALS", "HYOSUNG CORPORATION"],
    "ZHONGFU SHENYING": ["ZHONGFU", "中復神鷹", "中复神鹰"],
    "SGL CARBON": ["SGL", "SGL GROUP"],
    "HEXCEL": ["HEXCEL CORPORATION"],
    "SOLVAY": ["SOLVAY SA", "SOLVAY GROUP"],
    "ZOLTEK": ["ZOLTEK COMPANIES", "ZOLTEK CORP"],
  }


def _clean_name(name: str) -> str:
  text = unicodedata.normalize("NFKC", name).strip().upper()
  text = re.sub(r"\s+", " ", text)
  text = re.sub(r"[.,]", "", text)
  return text


def normalize_company_name(name: str | None) -> str:
  if not name:
    return ""
  cleaned = _clean_name(name)
  aliases = build_company_aliases()
  for canonical, variants in aliases.items():
    candidates = [_clean_name(canonical), *[_clean_name(v) for v in variants]]
    if cleaned in candidates:
      return canonical
    for candidate in candidates:
      if candidate and candidate in cleaned:
        return canonical
  return cleaned


def match_company_name(company: str | None, assignee: str | None) -> dict[str, Any]:
  normalized_company = normalize_company_name(company)
  normalized_assignee = normalize_company_name(assignee)
  if not normalized_company or not normalized_assignee:
    return {
      "matched": False,
      "normalized_company": normalized_company,
      "match_type": "no_match",
      "confidence": 0.0,
    }
  if normalized_company == normalized_assignee:
    return {
      "matched": True,
      "normalized_company": normalized_company,
      "match_type": "exact",
      "confidence": 1.0,
    }
  aliases = build_company_aliases()
  company_aliases = {normalized_company}
  assignee_aliases = {normalized_assignee}
  for canonical, variants in aliases.items():
    canon = _clean_name(canonical)
    if normalized_company == canon:
      company_aliases.add(canon)
      company_aliases.update(_clean_name(v) for v in variants)
    if normalized_assignee == canon:
      assignee_aliases.add(canon)
      assignee_aliases.update(_clean_name(v) for v in variants)
  if company_aliases & assignee_aliases:
    return {
      "matched": True,
      "normalized_company": normalized_company,
      "match_type": "alias",
      "confidence": 0.9,
    }
  if normalized_company in normalized_assignee or normalized_assignee in normalized_company:
    return {
      "matched": True,
      "normalized_company": normalized_company,
      "match_type": "partial",
      "confidence": 0.7,
    }
  return {
    "matched": False,
    "normalized_company": normalized_company,
    "match_type": "no_match",
    "confidence": 0.0,
  }
