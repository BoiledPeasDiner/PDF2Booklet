from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal

ItemKind = Literal["pdf", "image", "blank"]
Mode = Literal["booklet", "two_up"]

@dataclass
class Item:
    kind: ItemKind
    path: Optional[str] = None
    display_name: str = ""
    # 将来拡張用（v1ではUI未提供でもOK）
    rotation: int = 0  # 0/90/180/270

@dataclass
class Options:
    mode: Mode = "booklet"             # デフォルト＝ブックレット
    cover_preview: bool = True         # プレビュー/2-in-1にのみ適用
    grayscale: bool = False            # デフォルトOFF
    compress: bool = False             # デフォルトOFF

    # 画質設定（省サイズON/OFFで切替）
    dpi_normal: int = 220
    dpi_compress: int = 180            # ← 高画質寄り
    jpegq_normal: int = 92
    jpegq_compress: int = 85           # ← 高画質寄り

@dataclass
class PageRef:
    item_index: int
    pdf_page_index: Optional[int] = None  # PDFのみ
    is_blank: bool = False

@dataclass
class Spread:
    left: Optional[PageRef]
    right: Optional[PageRef]
