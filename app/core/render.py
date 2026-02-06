from __future__ import annotations
from typing import Dict, Optional, Tuple
import fitz  # PyMuPDF
from PIL import Image, ImageOps
from .types import Item, PageRef, Spread
from .errors import UserFacingError

# A4 landscape in inches
A4_LANDSCAPE_IN = (11.69, 8.27)

def blank_pil(dpi: int) -> Image.Image:
    w = int(A4_LANDSCAPE_IN[0] * dpi)
    h = int(A4_LANDSCAPE_IN[1] * dpi)
    return Image.new("RGB", (w, h), "white")

def open_pdf_checked(path: str) -> fitz.Document:
    try:
        doc = fitz.open(path)
    except Exception:
        raise UserFacingError(f"PDFを開けません: {path}")
    if getattr(doc, "needs_pass", False) and doc.needs_pass:
        doc.close()
        raise UserFacingError("パスワード保護PDFは非対応です。解除後のPDFを使用してください。")
    if getattr(doc, "is_encrypted", False) and doc.is_encrypted:
        doc.close()
        raise UserFacingError("パスワード保護PDFは非対応です。解除後のPDFを使用してください。")
    return doc

def render_page_to_pil(
    items: list[Item],
    pref: Optional[PageRef],
    dpi: int,
    grayscale: bool,
    pdf_cache: Optional[Dict[str, fitz.Document]] = None,
) -> Image.Image:
    if pref is None or pref.is_blank or pref.item_index < 0:
        im = blank_pil(dpi)
        return im.convert("L").convert("RGB") if grayscale else im

    it = items[pref.item_index]
    if it.kind == "blank":
        im = blank_pil(dpi)
    elif it.kind == "image":
        im = Image.open(it.path)
        im = ImageOps.exif_transpose(im)  # EXIF回転反映
        im = im.convert("RGB")
    elif it.kind == "pdf":
        if pdf_cache is not None:
            doc = pdf_cache.get(it.path)
            if doc is None:
                doc = open_pdf_checked(it.path)
                pdf_cache[it.path] = doc
        else:
            doc = open_pdf_checked(it.path)
        page = doc.load_page(pref.pdf_page_index)
        mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        if pdf_cache is None:
            doc.close()
    else:
        im = blank_pil(dpi)

    if grayscale:
        im = im.convert("L").convert("RGB")
    return im

def fit_rect(img_w: int, img_h: int, box_w: int, box_h: int) -> Tuple[int, int, int, int]:
    """縦横比維持でフィット（切れない）。戻り値は (x, y, w, h) in pixels."""
    if img_w <= 0 or img_h <= 0:
        return (0, 0, box_w, box_h)
    scale = min(box_w / img_w, box_h / img_h)
    w = int(img_w * scale)
    h = int(img_h * scale)
    x = (box_w - w) // 2
    y = (box_h - h) // 2
    return (x, y, w, h)

def render_spread_preview(
    items: list[Item],
    spread: Spread,
    dpi: int = 110,
    grayscale: bool = False,
) -> Image.Image:
    """右ペイン用：A4横キャンバス上に2-upしたプレビュー画像を生成"""
    canvas = blank_pil(dpi)
    W, H = canvas.size
    half_w = W // 2

    pdf_cache: Dict[str, fitz.Document] = {}
    try:
        left = render_page_to_pil(items, spread.left, dpi=dpi, grayscale=grayscale, pdf_cache=pdf_cache)
        right = render_page_to_pil(items, spread.right, dpi=dpi, grayscale=grayscale, pdf_cache=pdf_cache)

        lx, ly, lw, lh = fit_rect(left.width, left.height, half_w, H)
        canvas.paste(left.resize((lw, lh)), (lx, ly))

        rx, ry, rw, rh = fit_rect(right.width, right.height, half_w, H)
        canvas.paste(right.resize((rw, rh)), (half_w + rx, ry))
    finally:
        for d in pdf_cache.values():
            try:
                d.close()
            except Exception:
                pass
    return canvas
