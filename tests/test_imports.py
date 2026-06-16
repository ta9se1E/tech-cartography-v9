from tech_cartography import PROJECT_NAME, PROJECT_VERSION


def test_package_imports() -> None:
  assert PROJECT_NAME == "PatentScout AI v7"
  assert PROJECT_VERSION == "0.1.0"
