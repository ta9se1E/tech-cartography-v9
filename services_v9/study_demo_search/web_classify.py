"""Rule-based web company activity classification."""

from __future__ import annotations

from .constants import WEB_ACTIVITY_CATEGORIES

_RULES: dict[str, tuple[str, ...]] = {
  "技術・研究": ("研究", "開発", "技術", "特許", "論文", "試験", "評価", "research", "development"),
  "投資・生産": ("投資", "生産", "設備", "工場", "capacity", "production", "plant"),
  "提携・プロジェクト": ("提携", "共同", "プロジェクト", "連携", "partnership", "collaboration", "project"),
  "事業化": ("事業化", "商用", "上市", "launch", "commercial", "product"),
  "組織・人材": ("採用", "人事", "組織", "CEO", "executive", "hire", "organization"),
  "制度・規制": ("規制", "法令", "制度", "認可", "regulation", "compliance", "standard"),
}


def classify_web_activity(title: str, snippet: str) -> str:
  text = f"{title} {snippet}".lower()
  for category, tokens in _RULES.items():
    if any(token.lower() in text for token in tokens):
      return category
  return "その他"
