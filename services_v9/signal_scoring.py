"""Pure scoring helpers for the lightweight v9 signal watch app."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Sequence

from .signal_models import Signal, WatchProfile


def classify_status(score: float, previous_score: float | None) -> str:
  if previous_score is None:
    return "New"
  delta = score - previous_score
  if delta >= 0.10:
    return "Rising"
  if delta <= -0.10:
    return "Dropped"
  return "Stable"


def classify_action(score: float, status: str) -> str:
  if status in {"New", "Rising"} and score >= 0.75:
    return "Read Now"
  if score >= 0.55:
    return "Watch"
  return "Ignore"


def enrich_signals(signals: Sequence[Signal]) -> list[Signal]:
  enriched = []
  for signal in signals:
    status = classify_status(signal.score, signal.previous_score)
    action = classify_action(signal.score, status)
    enriched.append(replace(signal, status=status, action=action))
  return sorted(enriched, key=lambda item: (item.score, item.published_date, item.title), reverse=True)


def select_diverse_top_signals(
  signals: Sequence[Signal],
  top_n: int = 10,
  max_per_type: int = 4,
) -> list[Signal]:
  ranked = sorted(signals, key=lambda item: (item.score, item.published_date, item.title), reverse=True)
  if top_n <= 0:
    return []

  selected: list[Signal] = []
  selected_ids: set[str] = set()
  type_counts: Counter[str] = Counter()
  available_types = {signal.type for signal in ranked}
  required_types = [signal_type for signal_type in ("patent", "paper", "web") if signal_type in available_types]

  for signal_type in required_types:
    for signal in ranked:
      if signal.id in selected_ids or signal.type != signal_type:
        continue
      selected.append(signal)
      selected_ids.add(signal.id)
      type_counts[signal.type] += 1
      break

  for signal in ranked:
    if len(selected) >= top_n:
      break
    if signal.id in selected_ids:
      continue
    if type_counts[signal.type] >= max_per_type:
      continue
    selected.append(signal)
    selected_ids.add(signal.id)
    type_counts[signal.type] += 1

  if len(selected) < top_n:
    for signal in ranked:
      if len(selected) >= top_n:
        break
      if signal.id in selected_ids:
        continue
      selected.append(signal)
      selected_ids.add(signal.id)
      type_counts[signal.type] += 1

  return selected[:top_n]


def select_top_reads(signals: Sequence[Signal], limit: int = 3) -> list[Signal]:
  ranked = select_diverse_top_signals(signals, top_n=max(limit * 3, 10))
  read_now = [signal for signal in ranked if signal.action == "Read Now"]
  base = read_now if read_now else list(ranked)
  return base[:limit]


def summarize_status_buckets(signals: Sequence[Signal]) -> dict[str, list[Signal]]:
  buckets: dict[str, list[Signal]] = {
    "New": [],
    "Rising": [],
    "Dropped": [],
    "Stable": [],
  }
  for signal in signals:
    buckets.setdefault(signal.status, []).append(signal)
  return buckets


def format_score_delta(signal: Signal) -> str:
  if signal.previous_score is None:
    return "今回新規"
  delta = signal.score - signal.previous_score
  sign = "+" if delta >= 0 else ""
  return f"{sign}{delta:.2f}（前回 {signal.previous_score:.2f} → 今回 {signal.score:.2f}）"


def compute_theme_drift_alert(signals: Sequence[Signal], watch_profile: WatchProfile) -> dict[str, object]:
  reviewed = select_diverse_top_signals(signals, top_n=10)
  include_keywords = [keyword.lower() for keyword in watch_profile.include_keywords if keyword.strip()]
  if not reviewed:
    return {
      "level": "info",
      "message": "テーマずれ確認の対象シグナルがまだありません。",
      "matched_ratio": 0.0,
      "examples": [],
    }
  if not include_keywords:
    return {
      "level": "info",
      "message": "テーマずれ注意: 含めるキーワードが未設定のため、整合性をまだ判定できません。",
      "matched_ratio": 0.0,
      "examples": [],
    }

  low_overlap: list[Signal] = []
  for signal in reviewed:
    searchable = " ".join([signal.title, *signal.tags, *signal.companies]).lower()
    matches = sum(1 for keyword in include_keywords if keyword in searchable)
    if matches == 0:
      low_overlap.append(signal)

  low_ratio = len(low_overlap) / len(reviewed)
  matched_ratio = 1.0 - low_ratio
  if low_ratio >= 0.40:
    level = "warning"
    message = (
      f"テーマずれ注意: 上位{len(reviewed)}件のうち{len(low_overlap)}件が、"
      "現在の監視キーワードと一致しにくい状態です。"
    )
  elif low_overlap:
    level = "info"
    message = (
      f"テーマ整合は一部混在しています。上位{len(reviewed)}件のうち"
      f"{len(reviewed) - len(low_overlap)}件が現在の監視キーワードと一致しています。"
    )
  else:
    level = "success"
    message = "上位シグナルは現在の監視キーワードと概ね一致しています。"

  return {
    "level": level,
    "message": message,
    "matched_ratio": matched_ratio,
    "examples": [signal.title for signal in low_overlap[:3]],
  }


def suggest_watch_profile_updates(
  signals: Sequence[Signal],
  watch_profile: WatchProfile,
  limit: int = 5,
) -> list[str]:
  ranked = select_diverse_top_signals(signals, top_n=10)
  included = {keyword.lower() for keyword in watch_profile.include_keywords}
  excluded = {keyword.lower() for keyword in watch_profile.exclude_keywords}
  target_companies = {company.lower() for company in watch_profile.target_companies}
  suggestions: list[str] = []

  tag_counts = Counter(
    tag.lower()
    for signal in ranked
    for tag in signal.tags
    if tag.strip()
  )
  for tag, count in tag_counts.most_common():
    if count >= 2 and tag not in included and tag not in excluded:
      suggestions.append(f"add keyword: {tag}")
      break

  if "generic composite" not in excluded:
    suggestions.append("exclude noisy keyword: generic composite")

  company_counts = Counter(
    company
    for signal in ranked[:5]
    for company in signal.companies
    if company.strip()
  )
  for company, count in company_counts.most_common():
    if count >= 1 and company.lower() not in target_companies:
      suggestions.append(f"add company: {company}")
      break

  type_counts = Counter(signal.type for signal in ranked[:5])
  priority_text = " ".join(watch_profile.priority_rules).lower()
  if type_counts:
    top_type, top_count = type_counts.most_common(1)[0]
    if top_count >= 2 and top_type not in priority_text:
      suggestions.append(f"raise priority of source type: {top_type}")

  for source_type in watch_profile.source_types:
    source_scores = [signal.score for signal in ranked if signal.type == source_type]
    if not source_scores:
      suggestions.append(f"lower priority of irrelevant source: {source_type}")
      break
    if sum(source_scores) / len(source_scores) < 0.58:
      suggestions.append(f"lower priority of irrelevant source: {source_type}")
      break

  if not suggestions:
    suggestions.append("keep current watch profile: top signals align with the current source mix.")

  return suggestions[:limit]


def apply_watch_profile_suggestions(
  watch_profile: WatchProfile,
  suggestions: Sequence[str],
) -> WatchProfile:
  include_keywords = list(watch_profile.include_keywords)
  exclude_keywords = list(watch_profile.exclude_keywords)
  target_companies = list(watch_profile.target_companies)
  priority_rules = list(watch_profile.priority_rules)

  for suggestion in suggestions:
    if suggestion.startswith("add keyword:"):
      keyword = suggestion.split(":", 1)[1].strip()
      if keyword and keyword not in include_keywords:
        include_keywords.append(keyword)
    elif suggestion.startswith("exclude noisy keyword:"):
      keyword = suggestion.split(":", 1)[1].strip()
      if keyword and keyword not in exclude_keywords:
        exclude_keywords.append(keyword)
    elif suggestion.startswith("add company:"):
      company = suggestion.split(":", 1)[1].strip()
      if company and company not in target_companies:
        target_companies.append(company)
    elif suggestion.startswith("raise priority of source type:"):
      source_type = suggestion.split(":", 1)[1].strip()
      rule = f"次回の週次ダイジェストでは {source_type} を優先的に確認する。"
      if source_type and rule not in priority_rules:
        priority_rules.append(rule)
    elif suggestion.startswith("lower priority of irrelevant source:"):
      source_type = suggestion.split(":", 1)[1].strip()
      rule = f"{source_type} のスコアが低い状態が続く場合は優先度を下げる。"
      if source_type and rule not in priority_rules:
        priority_rules.append(rule)

  return WatchProfile(
    theme=watch_profile.theme,
    include_keywords=include_keywords,
    exclude_keywords=exclude_keywords,
    target_companies=target_companies,
    source_types=list(watch_profile.source_types),
    countries=list(watch_profile.countries),
    cadence=watch_profile.cadence,
    priority_rules=priority_rules,
  )


def build_diversity_counts(signals: Sequence[Signal]) -> dict[str, int]:
  top_signals = select_diverse_top_signals(signals, top_n=10)
  counts = Counter(signal.type for signal in top_signals)
  return {signal_type: counts.get(signal_type, 0) for signal_type in ("patent", "paper", "web", "company")}
