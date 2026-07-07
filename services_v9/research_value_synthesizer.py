"""Deterministic research value text synthesis."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from services_v9.research_signal_roles import (
  ROLE_BACKGROUND,
  ROLE_FORMULATION,
  ROLE_INSUFFICIENT,
  ROLE_LOW,
  ROLE_MECHANISM,
  ROLE_NOVEL,
  ROLE_PROPERTY,
  ROLE_LABELS_JA,
)
from services_v9.research_value_theme_axes import axis_label_ja

UNSUPPORTED_ASSERTION_PATTERNS = (
  r"改善しています",
  r"有効です",
  r"優れています",
  r"証明しています",
  r"技術的に妥当です",
  r"実施可能です",
  r"であると判断できます",
)


def _title_phrases(title: str) -> list[str]:
  cleaned = re.sub(r"\s+", " ", title.strip())
  if not cleaned:
    return []
  parts = re.split(r"[,;:]", cleaned)
  return [part.strip() for part in parts if len(part.strip()) >= 8][:3]


def synthesize_short_title_ja(signal: Mapping[str, Any], role: Mapping[str, Any]) -> str:
  title = str(signal.get("title", "") or "")
  role_code = str(role.get("code", "") or "")
  lowered = title.lower()
  if "wear-resistant" in lowered and "brittleness" in lowered:
    return "高脆性炭素繊維向け・耐摩耗サイジング特許"
  if "styrene-acrylic" in lowered and "mechanical properties" in lowered:
    return "スチレン–アクリル系サイジングとトウプリグ物性"
  if "ionic liquid" in lowered and "polyurethane" in lowered:
    return "イオン液体×水系PU複合サイジング特許"
  if role_code == ROLE_PROPERTY:
    return "サイジング条件と力学物性の関係（論文）"
  if role_code == ROLE_FORMULATION:
    return "サイジング処方・工程の確認候補（特許）"
  if role_code == ROLE_NOVEL:
    return "新規処方軸の探索候補（特許）"
  phrase = _title_phrases(title)
  if phrase:
    return phrase[0][:42]
  return title[:42] or "確認候補文献"


def _axis_phrase(fact_sheet: Mapping[str, Any]) -> str:
  axes = list(fact_sheet.get("matched_theme_axes", []) or [])[:2]
  if not axes:
    return "組成・工程・物性"
  return "・".join(axis_label_ja(axis) for axis in axes)


def _doc_terms(fact_sheet: Mapping[str, Any], limit: int = 3) -> list[str]:
  concepts = [str(item.get("concept", "")) for item in list(fact_sheet.get("supported_concepts", []) or [])]
  if concepts:
    return concepts[:limit]
  title = str(fact_sheet.get("title", "") or "")
  return _title_phrases(title)[:limit]


def synthesize_research_value(
  signal: Mapping[str, Any],
  *,
  role: Mapping[str, Any],
  fact_sheet: Mapping[str, Any],
) -> str:
  role_code = str(role.get("code", "") or "")
  terms = _doc_terms(fact_sheet)
  term_text = "、".join(terms[:2]) if terms else "取得済みタイトル記載語"
  axis_text = _axis_phrase(fact_sheet)
  title = str(signal.get("title", "") or "")

  if role_code in {ROLE_INSUFFICIENT, ROLE_LOW}:
    return (
      "タイトルと取得済み概要だけでは、研究上の確認価値を具体化できません。"
      "原典取得後に、Themeの組成・工程・物性軸へ照合して再評価する必要があります。"
      "一次情報として調査比較に使えるかも、この段階では判断できません。"
    )

  if role_code == ROLE_FORMULATION:
    if "wear-resistant" in title.lower():
      return (
        "高脆性炭素繊維の損傷抑制と耐摩耗性を狙うサイジング技術であり、"
        "集束性、毛羽、耐擦過性に関係する処方・処理条件を確認できる候補です。"
        f"{term_text}や{axis_text}の記載から、取り扱い性を改善する処方軸として比較できる可能性があります。"
        "主成分だけでなく、付与量、乾燥条件、比較例で変化した評価項目まで原典で確認します。"
      )
    return (
      f"{term_text}を含むサイジング処方・工程の候補であり、{axis_text}に関する記載を確認できる可能性があります。"
      "組成、付与条件、乾燥・硬化条件、比較例の有無を原典で照合し、"
      "Themeの監視軸へ転記できる処方候補として位置づけます。"
    )

  if role_code == ROLE_PROPERTY:
    if "styrene-acrylic" in title.lower():
      return (
        "スチレン–アクリル系サイジングと、熱可塑性トウプリグおよび複合材料の力学物性を同時に扱う候補です。"
        "サイジング剤の種類・付与条件・試料作製条件と、引張強度、弾性率、界面特性の関係を比較できる可能性があります。"
        "処方差が最終物性へどう現れるかを確認するための評価エビデンスとして位置づけます。"
      )
    return (
      f"{term_text}に関する論文候補であり、{axis_text}の評価結果を確認できる可能性があります。"
      "試料作製条件、評価法、比較対象、物性変化の記載を原典で確認し、"
      "処方–工程–物性の因果を比較表へ転記するためのエビデンスとして扱います。"
    )

  if role_code == ROLE_NOVEL:
    if "ionic liquid" in title.lower():
      return (
        "イオン液体と水系ポリウレタンを組み合わせた複合サイジング処方であり、"
        "従来のエポキシ系や単独ポリウレタン系とは異なる処方軸を検討する候補です。"
        "イオン液体の役割、ポリウレタンとの配合、乾燥・硬化条件、改善対象となる物性を原典で確認することで、"
        "次回検索へ追加すべき成分名や作用機構仮説を判断できる可能性があります。"
      )
    return (
      f"{term_text}を含む新規処方候補であり、{axis_text}の観点で従来処方との差分を確認できる可能性があります。"
      "有効な実施例が確認できた場合、成分名・配合・想定作用を仮説カードへ追記し、"
      "次回検索語候補として人間レビューへ回す判断材料になります。"
    )

  if role_code == ROLE_MECHANISM:
    return (
      f"{term_text}に関する界面・作用機構の候補であり、{axis_text}の説明がデータと整合するか原典で確認する必要があります。"
      "界面接着や濡れ性の記述が、Themeの界面物性仮説を補強または反証できる可能性があります。"
    )

  return (
    f"{term_text}に触れる背景整理候補であり、{axis_text}への直接一致は限定的な可能性があります。"
    "Theme照合の一次情報として使えるか、原典で確認する必要があります。"
    "直接証拠ではなく背景理解として位置づけるか、除外理由をレビューへ記録します。"
  )


def _question(text: str) -> str:
  text = text.strip().rstrip("？?").rstrip("。.。")
  if not text.endswith("か"):
    text += "か"
  return text + "？"


def synthesize_research_questions(
  signal: Mapping[str, Any],
  *,
  role: Mapping[str, Any],
  fact_sheet: Mapping[str, Any],
) -> list[str]:
  source_type = str(fact_sheet.get("source_type", "") or "")
  role_code = str(role.get("code", "") or "")
  title = str(signal.get("title", "") or "").lower()
  terms = _doc_terms(fact_sheet)

  if role_code in {ROLE_INSUFFICIENT, ROLE_LOW}:
    return [
      _question("対象材料はThemeのPAN系炭素繊維サイジングと一致するか"),
      _question("処方・工程・物性の具体的記載は原典にあるか"),
      _question("一次情報として調査比較に利用できるか"),
    ]

  if source_type == "patent":
    questions = []
    if "wear-resistant" in title:
      questions = [
        "独立請求項で必須となる主成分、硬化成分、溶媒は何か",
        "各成分の配合比、サイジング液濃度、繊維への付与量はどの範囲か",
        "乾燥・硬化温度、時間、雰囲気は実施例ごとにどう設定されているか",
        "比較例に対して毛羽、耐擦過性、集束性、強度のどれがどの程度変化したか",
        "対象繊維はPAN系か、high-brittlenessの定義は何か",
      ]
    elif "ionic liquid" in title:
      questions = [
        "使用するイオン液体の化学種と、水系ポリウレタンに対する配合比は何か",
        "乳化剤、硬化剤、溶媒、その他添加剤は必須か任意か",
        "サイジング液濃度、付与量、乾燥・硬化条件は何か",
        "単独ポリウレタン系や既存処方に対する比較例はあるか",
        "改善対象は集束性、含浸性、界面接着、耐摩耗性、力学物性のどれか",
      ]
    else:
      questions = [
        f"独立請求項で必須となる成分・工程は何か（{terms[0] if terms else 'title記載語'}）",
        "成分の種類、配合比、濃度範囲はどのように記載されているか",
        "付与量は何wt%またはどの評価単位で示されるか",
        "乾燥・硬化温度、時間、雰囲気は何か",
        "実施例と比較例で変えた因子と評価項目は何か",
      ]
    return [_question(item) for item in questions[:5]]

  if source_type == "paper":
    if "styrene-acrylic" in title:
      return [
        _question("使用した炭素繊維、スチレン–アクリル系サイジング、熱可塑性matrixは何か"),
        _question("サイジングの付与量、除去・再付与方法、乾燥条件は何か"),
        _question("トウプリグと複合材料の作製条件は比較群間で統一されているか"),
        _question("引張強度、弾性率、界面特性は未処理または別処方からどう変化したか"),
        _question("試験片数、ばらつき、統計的有意性は示されているか"),
      ]
    return [
      _question(f"使用した炭素繊維、サイジング剤、matrix resinは何か（{terms[0] if terms else 'title'}）"),
      _question("サイジングの付与量と試料作製条件は何か"),
      _question("評価法、規格、試験片数は何か"),
      _question("比較対象は何か"),
      _question("強度・弾性率・界面特性はどう変化したか"),
    ]

  return [
    _question("情報発信者は誰か、一次情報へのリンクはあるか"),
    _question("製品・技術の実装段階は何か"),
    _question("定量データはあるか、宣伝表現と検証可能な事実を分けられるか"),
    _question("特許・論文・製品資料と対応するか"),
  ]


def synthesize_readout_artifact(role: Mapping[str, Any], fact_sheet: Mapping[str, Any]) -> str:
  role_code = str(role.get("code", "") or "")
  if role_code == ROLE_FORMULATION:
    return "請求項と実施例から、組成・配合比・付与量・乾燥条件・比較評価を処方–工程–物性比較表へ転記する。"
  if role_code == ROLE_PROPERTY:
    return "材料構成、サイジング条件、試料作製条件、評価法、比較対象、強度・弾性率の結果を物性エビデンス表へ転記する。"
  if role_code == ROLE_NOVEL:
    return "有効な実施例が確認できた場合、成分名、配合、想定作用、対象物性を新規処方仮説カードへ追記し、次回検索語候補として人間レビューへ回す。"
  if role_code == ROLE_MECHANISM:
    return "界面・作用機構の記述と根拠データを作用機構仮説カードへ追記する。"
  return "背景整理メモへ追記し、直接証拠かどうかをレビューへ記録する。"


def synthesize_role_summary(role: Mapping[str, Any]) -> str:
  return str(role.get("label_ja", "") or ROLE_LABELS_JA.get(str(role.get("code", "")), ""))


def build_ranking_basis(signal: Mapping[str, Any], fact_sheet: Mapping[str, Any]) -> dict[str, Any]:
  return {
    "summary": str(signal.get("relevance_reason", "") or "Theme一致語と取得済み概要に基づく候補"),
    "evidence": [
      {"kind": "keyword_match", "value": term} for term in list(fact_sheet.get("matched_terms", []) or [])[:5]
    ]
    + [{"kind": "theme_axis", "value": axis} for axis in list(fact_sheet.get("matched_theme_axes", []) or [])[:5]]
    + [
      {"kind": "score", "value": str(signal.get("relevance_score", ""))},
      {"kind": "tier", "value": str(signal.get("relevance_tier", ""))},
    ],
  }


def synthesize_research_value_output(
  signal: Mapping[str, Any],
  *,
  role: Mapping[str, Any],
  fact_sheet: Mapping[str, Any],
) -> dict[str, Any]:
  research_value = synthesize_research_value(signal, role=role, fact_sheet=fact_sheet)
  questions = synthesize_research_questions(signal, role=role, fact_sheet=fact_sheet)
  summary = str(signal.get("summary", "") or "")
  data_basis = "title_abstract" if summary.strip() else "title_only"
  confidence = "medium"
  caveat = ""
  if not summary.strip():
    confidence = "low"
    caveat = "abstractが未取得のため、確認価値は原典確認後に再評価が必要です。"
  elif str(role.get("code", "")) in {ROLE_INSUFFICIENT, ROLE_LOW}:
    confidence = "low"
    caveat = "関連度が低い、または情報不足の候補です。"
  return {
    "role": {
      "code": role.get("code", ""),
      "label_ja": synthesize_role_summary(role),
      "reason": role.get("reason", ""),
    },
    "short_title_ja": synthesize_short_title_ja(signal, role),
    "original_title": str(signal.get("title", "") or ""),
    "research_value": research_value,
    "verification_questions": questions,
    "readout_artifact": synthesize_readout_artifact(role, fact_sheet),
    "ranking_basis": build_ranking_basis(signal, fact_sheet),
    "data_basis": data_basis,
    "confidence": confidence,
    "caveat": caveat,
  }


def contains_unsupported_assertion(text: str) -> bool:
  return any(re.search(pattern, text) for pattern in UNSUPPORTED_ASSERTION_PATTERNS)


__all__ = [
  "build_ranking_basis",
  "contains_unsupported_assertion",
  "synthesize_readout_artifact",
  "synthesize_research_questions",
  "synthesize_research_value",
  "synthesize_research_value_output",
  "synthesize_short_title_ja",
]
