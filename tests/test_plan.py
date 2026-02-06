from app.core.plan import make_booklet_spreads, make_preview_spreads, pad_to_multiple_of_4
from app.core.types import PageRef

def test_pad_to_multiple_of_4():
    pages = [PageRef(item_index=0, pdf_page_index=i) for i in range(5)]
    padded = pad_to_multiple_of_4(pages)
    assert len(padded) % 4 == 0
    assert len(padded) == 8

def test_preview_cover_adds_blank():
    pages = [PageRef(item_index=0, pdf_page_index=i) for i in range(3)]
    spreads = make_preview_spreads(pages, cover_preview=True)
    assert len(spreads) == 2
    assert spreads[0].left.is_blank is True
    assert spreads[0].right.pdf_page_index == 0

def test_booklet_order_8pages():
    pages = [PageRef(item_index=0, pdf_page_index=i) for i in range(8)]
    spreads = make_booklet_spreads(pages)
    assert len(spreads) == 4
    assert spreads[0].left.pdf_page_index == 7
    assert spreads[0].right.pdf_page_index == 0
