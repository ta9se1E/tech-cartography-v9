"""v8 text rendering helpers — safe str / list display (Phase 27H.1)."""

from __future__ import annotations

from html import escape
from typing import Any


def normalize_text_items(value: Any) -> list[str]:
  """Normalize str / list / None for bullet display without splitting strings char-by-char."""
  if value is None:
    return []
  if isinstance(value, str):
    text = value.strip()
    return [text] if text else []
  if isinstance(value, (list, tuple)):
    items: list[str] = []
    for item in value:
      text = str(item).strip()
      if text:
        items.append(text)
    return items
  text = str(value).strip()
  return [text] if text else []


def render_bullet_items(items: Any, *, empty_message: str = "") -> str:
  normalized = normalize_text_items(items)
  if not normalized:
    return empty_message or "（表示する項目がありません）"
  return "\n".join(f"- {item}" for item in normalized)


def render_next_action_card(
  title: str,
  next_actions: Any,
  *,
  empty_message: str = "次に行う操作はまだありません。",
) -> str:
  items = normalize_text_items(next_actions)
  safe_title = escape(title)
  if not items:
    body = f"<li>{escape(empty_message)}</li>"
  else:
    body = "".join(f"<li>{escape(item)}</li>" for item in items)
  return f'<div class="tc-card-box"><b>{safe_title}</b><ul>{body}</ul></div>'
