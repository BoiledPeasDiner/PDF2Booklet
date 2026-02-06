from __future__ import annotations
from typing import List
from .types import PageRef, Spread

def pad_to_even(pages: List[PageRef]) -> List[PageRef]:
    if len(pages) % 2 == 1:
        pages.append(PageRef(item_index=-1, is_blank=True))
    return pages

def pad_to_multiple_of_4(pages: List[PageRef]) -> List[PageRef]:
    while len(pages) % 4 != 0:
        pages.append(PageRef(item_index=-1, is_blank=True))
    return pages

def make_preview_spreads(pages: List[PageRef], cover_preview: bool) -> List[Spread]:
    """右ペインのプレビュー用（常に通常順2-up）。表紙ONなら先頭に空白を1枚足す。"""
    p = list(pages)
    if cover_preview:
        p = [PageRef(item_index=-1, is_blank=True)] + p
    p = pad_to_even(p)

    spreads: List[Spread] = []
    for i in range(0, len(p), 2):
        spreads.append(Spread(left=p[i], right=p[i + 1]))
    return spreads

def make_two_up_spreads_for_output(pages: List[PageRef], cover_preview: bool) -> List[Spread]:
    """2-in-1出力用（プレビューと同一ロジック）"""
    return make_preview_spreads(pages, cover_preview)

def make_booklet_spreads(pages: List[PageRef]) -> List[Spread]:
    """ブックレット面付け（A4横ページに2-upで配置する前提のスプレッド列を返す）"""
    p = pad_to_multiple_of_4(list(pages))
    n = len(p)
    spreads: List[Spread] = []

    # 1シート = 表裏で2スプレッド
    for i in range(n // 4):
        # 表
        left = p[n - 1 - 2 * i]
        right = p[0 + 2 * i]
        spreads.append(Spread(left=left, right=right))
        # 裏
        left2 = p[1 + 2 * i]
        right2 = p[n - 2 - 2 * i]
        spreads.append(Spread(left=left2, right=right2))
    return spreads
