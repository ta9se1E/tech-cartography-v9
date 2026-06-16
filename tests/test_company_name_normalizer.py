"""Tests for company name normalizer."""

from tech_cartography.evidence.company_name_normalizer import match_company_name, normalize_company_name


def test_toray_aliases() -> None:
  assert normalize_company_name("TORAY") == "TORAY"
  assert normalize_company_name("TORAY INDUSTRIES") == "TORAY"
  assert normalize_company_name("東レ") == "TORAY"


def test_mitsubishi_aliases() -> None:
  assert normalize_company_name("MITSUBISHI CHEMICAL") == "MITSUBISHI CHEMICAL"
  assert normalize_company_name("三菱ケミカル") == "MITSUBISHI CHEMICAL"


def test_match_company_name_exact() -> None:
  result = match_company_name("TORAY INDUSTRIES", "TORAY")
  assert result["matched"] is True
  assert result["match_type"] in {"exact", "alias"}
