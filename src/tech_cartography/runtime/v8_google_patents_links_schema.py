"""Google Patents link schema (Phase 27S.0)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

GOOGLE_PATENTS_SAFETY_NOTICES: tuple[str, ...] = (
  "Google PatentsのページからユーザーがPDFを確認・取得します — 自動スクレイピング・大量ダウンロードは行いません。",
  "直接PDF URLは推測生成しません — ページ内のDownload PDFから取得してください。",
  "このPhaseではPDF本文解析はまだ行いません — 次Phaseで description / examples を構造化します。",
  "Evidence Mapは証明ではなく裏取り候補、Gapは弱点ではなく未確認事項です。",
  "FTO、侵害、有効性判断、権利範囲評価は行いません。",
)

PDF_DOWNLOAD_INSTRUCTION = (
  "Google Patentsで公報を開き、ページ内の Download PDF からPDFを取得してください。"
  " 取得したPDFは、このTop5 Deep Dive内のPDFアップロード欄に投入してください。"
)

PDF_UPLOAD_NEXT_ACTION = "PDFを取得してアップロード"

VALID_PDF_UPLOAD_STATUSES: tuple[str, ...] = (
  "未アップロード",
  "アップロード済み",
)


@dataclass
class GooglePatentsLink:
  case_id: str
  publication_number: str
  title: str = ""
  assignee: str = ""
  year: str = ""
  google_patents_url: str = ""
  google_patents_search_url: str = ""
  pdf_download_instruction: str = PDF_DOWNLOAD_INSTRUCTION
  pdf_upload_status: str = "未アップロード"
  next_action: str = PDF_UPLOAD_NEXT_ACTION
  rank: int = 0

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class GooglePatentsLinksExport:
  case_id: str
  output_dir: str
  csv_path: str
  md_path: str
  link_count: int = 0

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
