"""Japanese copy policy for Delivery Hub outputs (Phase 24.1.1)."""

from __future__ import annotations

import re
from typing import Any

# Backward-compatible constant; prefer ja_preview_only_notice() in user-facing body.
PREVIEW_ONLY_NOTICE_EN = "Preview only. Email sending is disabled in this phase."

_STATUS_MAP: dict[str, tuple[str, str]] = {
  "preview_only": (
    "プレビューのみ",
    "この画面からはメール送信されません。",
  ),
  "draft_saved": (
    "下書き保存済み",
    "メール草稿をOutboxに保存しました。送信前に人間が内容を確認してください。",
  ),
  "blocked_missing_recipient": (
    "送信停止：宛先未設定",
    "宛先が設定されていないため送信しません。",
  ),
  "blocked_missing_adapter": (
    "送信停止：メール送信設定なし",
    "SMTP設定がないため送信しません。草稿のみ保存します。",
  ),
  "sent": (
    "送信済み",
    "明示的な送信オプションにより送信されました。",
  ),
  "failed": (
    "送信失敗",
    "送信処理中にエラーが発生しました。",
  ),
}

_WATCH_PRIORITY_MAP = {
  "high": "高",
  "medium": "中",
  "low": "低",
}

_WATCH_TYPE_MAP = {
  "national_project_signal": "国家プロジェクトシグナル",
  "patent_paper_web_signal": "特許×論文×Webシグナル",
  "money_signal": "資金・予算シグナル",
  "ir_disclosure_signal": "IR・開示シグナル",
  "evidence_gap": "エビデンスギャップ",
  "company_signal": "企業シグナル",
  "local_news_signal": "地域ニュースシグナル",
}

_CONFIDENCE_MAP = {
  "high": "高",
  "medium": "中",
  "low": "低",
  "weak": "弱",
}

_SOURCE_QUALITY_MAP = {
  "high": "高",
  "medium": "中",
  "low": "低",
}

_NEXT_ACTION_MAP: dict[str, str] = {
  "Verify public funding / project page and thematic overlap with patent claims.": (
    "公的プロジェクトの原典ページを確認し、事業名・実施者・期間・対象技術が"
    "対象特許のClaim Elementと同じ範囲を指しているか確認してください。"
  ),
  "Open source URLs and verify original documents.": (
    "出典URLを開き、原典資料の本文を確認してください。"
  ),
  "Confirm claim element / paper / web signal terminology alignment.": (
    "Claim Element、論文候補、Webシグナルで使われている技術語が"
    "同じ意味で使われているか確認してください。"
  ),
  "Do not use for FTO, infringement, or validity conclusions.": (
    "FTO調査、侵害判断、有効性判断には使用しないでください。"
  ),
}

_JA_CAVEATS: list[str] = [
  "このレポートは最終結論ではありません。",
  "Webシグナルは「確認候補」であり、事実関係や特許との関係を断定するものではありません。",
  "論文候補は技術的な裏取りの参考情報であり、特許請求項を証明するものではありません。",
  "本レポートはFTO調査、侵害判断、有効性判断、法的見解ではありません。",
  "IR・決算資料・開示情報は、原典資料レベルでの確認が必要です。",
  "公的予算・国家プロジェクトに関する情報は、原典ページで事業名・実施者・期間・対象技術を確認してください。",
  "Synthetic demo signal は、必ず Synthetic demo signal と明記してください。",
  "このPhaseではメール送信は行いません。表示・下書き保存のみです。",
]

_ENGLISH_NOTES: list[str] = [
  "Web signals are signal candidates, not final conclusions.",
  "Papers are supporting evidence candidates, not proof of patent claims.",
  "This is not FTO, infringement, or validity analysis.",
]

_DOMAIN_AGENCY_MAP = {
  "nedo.go.jp": "NEDO",
  "jst.go.jp": "JST",
  "meti.go.jp": "METI",
}

_AGENCY_TOKENS = (
  ("NEDO", ("nedo", "新エネルギー")),
  ("JST", ("jst", "科学技術振興機構")),
  ("METI", ("meti", "経済産業省")),
)


def ja_status_label(status: str) -> str:
  return _STATUS_MAP.get(str(status or "").strip(), (status or "不明", ""))[0]


def ja_status_description(status: str) -> str:
  return _STATUS_MAP.get(str(status or "").strip(), ("", ""))[1]


def ja_status_message(status: str) -> str:
  label, desc = _STATUS_MAP.get(str(status or "").strip(), ("不明", ""))
  if label and desc:
    return f"{label}：{desc}"
  return label or desc or str(status)


def ja_confidence_label(confidence: str) -> str:
  key = str(confidence or "").strip().lower()
  return _CONFIDENCE_MAP.get(key, confidence or "不明")


def ja_watch_priority_label(priority: str) -> str:
  key = str(priority or "").strip().lower()
  return _WATCH_PRIORITY_MAP.get(key, priority or "不明")


def ja_watch_type_label(watch_type: str) -> str:
  key = str(watch_type or "").strip().lower()
  return _WATCH_TYPE_MAP.get(key, watch_type or "不明")


def ja_source_quality_label(source_quality: str) -> str:
  key = str(source_quality or "").strip().lower()
  return _SOURCE_QUALITY_MAP.get(key, source_quality or "不明")


def ja_caveats() -> list[str]:
  return list(_JA_CAVEATS)


def ja_preview_only_notice() -> str:
  return "プレビューのみ：この画面・このPhaseではメール送信されません。送信前に人間が内容を確認してください。"


def ja_preview_only_notice_short() -> str:
  return "プレビューのみ。この段階ではメール送信は行いません。"


def ja_next_action(action: str, watch_type: str | None = None) -> str:
  raw = str(action or "").strip()
  if not raw:
    if watch_type in {"national_project_signal", "money_signal"}:
      return _NEXT_ACTION_MAP[
        "Verify public funding / project page and thematic overlap with patent claims."
      ]
    return "次に確認すべき事項を人手で整理してください。"
  if raw in _NEXT_ACTION_MAP:
    return _NEXT_ACTION_MAP[raw]
  lowered = raw.lower()
  if "verify public funding" in lowered or "project page" in lowered:
    return _NEXT_ACTION_MAP[
      "Verify public funding / project page and thematic overlap with patent claims."
    ]
  if "open source url" in lowered or "verify original" in lowered:
    return _NEXT_ACTION_MAP["Open source URLs and verify original documents."]
  if "claim element" in lowered and "terminology" in lowered:
    return _NEXT_ACTION_MAP[
      "Confirm claim element / paper / web signal terminology alignment."
    ]
  if "fto" in lowered or "infringement" in lowered or "validity" in lowered:
    return _NEXT_ACTION_MAP["Do not use for FTO, infringement, or validity conclusions."]
  return raw


def clean_digest_title(title: str) -> str:
  text = str(title or "").strip()
  if not text:
    return ""

  is_pdf = bool(re.search(r"\[PDF\]", text, flags=re.IGNORECASE))
  text = re.sub(r"\[PDF\]\s*", "", text, flags=re.IGNORECASE)
  text = re.sub(r"\s*-\s*NEDO\s*$", "", text, flags=re.IGNORECASE)
  text = re.sub(r"\s*-\s*JST\s*$", "", text, flags=re.IGNORECASE)
  text = re.sub(r"\s*-\s*METI\s*$", "", text, flags=re.IGNORECASE)
  text = re.sub(r"^\(添付-\d+\)\s*", "", text)
  text = re.sub(r"\s+", " ", text).strip()

  if is_pdf and not text.endswith("(PDF)"):
    text = f"{text}（PDF）"
  if re.search(r"用語集|プロジェクト用語", text):
    return "プロジェクト用語集（参考資料）"
  return text


def _agency_from_domain(domain: str) -> str:
  lowered = str(domain or "").strip().lower()
  for key, label in _DOMAIN_AGENCY_MAP.items():
    if key in lowered:
      return label
  return ""


def _agency_from_text(text: str) -> str:
  combined = str(text or "").lower()
  for label, tokens in _AGENCY_TOKENS:
    if any(token in combined for token in tokens):
      return label
  return ""


def build_digest_item_title(item: dict[str, Any]) -> str:
  web_title = str(item.get("related_web_signal_title") or "").strip()
  domain = str(item.get("related_web_signal_domain") or "").strip()
  theme = str(item.get("watch_theme") or "").strip()
  watch_type = str(item.get("watch_type") or "").strip()
  paper = str(item.get("related_paper_title") or "").strip()
  link_type = str(item.get("link_type") or "").strip()

  agency = _agency_from_domain(domain) or _agency_from_text(web_title)

  if web_title:
    cleaned = clean_digest_title(web_title)
    if len(cleaned) > 72:
      cleaned = cleaned[:72].rstrip() + "…"
    title = f"{agency}: {cleaned}" if agency else cleaned
    if paper:
      short_paper = paper[:40] + ("…" if len(paper) > 40 else "")
      title = f"{title}（関連論文: {short_paper}）"
    elif link_type:
      title = f"{title}（{link_type}）"
    return title

  if paper:
    cleaned = paper[:72] + ("…" if len(paper) > 72 else "")
    return f"関連論文: {cleaned}"

  if theme:
    type_label = ja_watch_type_label(watch_type) if watch_type else ""
    return f"{theme}（{type_label}）" if type_label else theme
  return "（テーマ不明）"


def ja_why_it_matters(text: str, watch_type: str | None = None) -> str:
  raw = str(text or "").strip()
  if not raw:
    return "—"
  lowered = raw.lower()
  if (
    "nedo" in lowered
    or "jst" in lowered
    or "meti" in lowered
    or "public sources" in lowered
    or "公的ソース" in raw
  ):
    return (
      "NEDO/JST/METIなどの公的ソースで、炭素繊維・CFRP・PAN系技術に関する"
      "研究開発シグナルが確認されています。対象特許の技術領域と周辺テーマが"
      "重なるため、次に原典確認すべき候補です。"
    )
  if "evidence map" in lowered:
    return "Evidence Mapの合成結果から、追加の手動確認が必要な論点が示されています（要確認）。"
  return raw


def ja_evidence_basis(text: str) -> str:
  raw = str(text or "").strip()
  if not raw:
    return "—"
  parts: list[str] = []
  for segment in raw.split(";"):
    segment = segment.strip()
    if not segment:
      continue
    if segment.startswith("title="):
      parts.append(f"タイトル={segment[6:].strip()}")
    elif segment.startswith("domain="):
      parts.append(f"ドメイン={segment[7:].strip()}")
    elif segment.startswith("quality="):
      parts.append(f"ソース品質={ja_source_quality_label(segment[8:].strip())}")
    elif segment.startswith("link_type="):
      parts.append(f"リンク種別={segment[10:].strip()}")
    elif segment.startswith("terms="):
      parts.append(f"関連語={segment[6:].strip()}")
    else:
      parts.append(segment)
  joined = "、".join(parts) if parts else raw
  if len(joined) > 180:
    return joined[:180].rstrip() + "（要確認）"
  return joined


def render_japanese_important_caveats(*, include_english_notes: bool = False) -> str:
  lines = ["## 重要な注意事項", ""]
  for caveat in ja_caveats():
    lines.append(f"- {caveat}")
  if include_english_notes:
    lines.extend(["", "## English Notes", ""])
    for note in _ENGLISH_NOTES:
      lines.append(f"- {note}")
  return "\n".join(lines)


def ja_digest_subject(publication_number: str, date_label: str) -> str:
  return f"[Tech Cartography] 週次インテリジェンスDigest - {publication_number} - {date_label}"


def ja_email_draft_preamble() -> str:
  return (
    "このメールは Tech Cartography による週次インテリジェンスDigestの下書きです。\n"
    "このPhaseでは自動送信は行わず、送信前に人間が内容を確認する前提です。"
  )


def ja_ui_send_disabled_notice() -> str:
  return "UIからのメール送信は無効です。送信する場合はCLIで --send-email を明示してください。"
