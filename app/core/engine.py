from __future__ import annotations
import io, json, os, shutil
from typing import Callable, Optional, Dict
import fitz  # PyMuPDF
from PIL import Image

from .types import Item, Options, PageRef
from .errors import UserFacingError, is_heic, is_supported_image, is_pdf
from .plan import make_two_up_spreads_for_output, make_booklet_spreads
from .render import open_pdf_checked, render_page_to_pil

# A4 landscape in points
A4_LANDSCAPE_W_PT = 842
A4_LANDSCAPE_H_PT = 595

def validate_and_build_items(raw_items: list[dict]) -> list[Item]:
    items: list[Item] = []
    for r in raw_items:
        kind = r["kind"]
        if kind == "blank":
            items.append(Item(kind="blank", path=None, display_name="(空白)"))
            continue

        path = r.get("path")
        if not path or not os.path.isfile(path):
            raise UserFacingError(f"ファイルが存在しません: {path}")

        if is_heic(path):
            raise UserFacingError("HEIC(.heic/.heif) は未対応です。JPG/PNGに変換してから追加してください。")

        if kind == "pdf":
            if not is_pdf(path):
                raise UserFacingError(f"PDFではありません: {path}")
        elif kind == "image":
            if not is_supported_image(path):
                raise UserFacingError(f"画像形式はJPG/PNGのみ対応です: {path}")
        else:
            raise UserFacingError(f"未知のkind: {kind}")

        dn = os.path.basename(path)
        items.append(Item(kind=kind, path=path, display_name=dn))
    return items

def build_logical_pages(items: list[Item]) -> list[PageRef]:
    pages: list[PageRef] = []
    pdf_cache: Dict[str, fitz.Document] = {}
    try:
        for idx, it in enumerate(items):
            if it.kind == "blank":
                pages.append(PageRef(item_index=idx, is_blank=True))
            elif it.kind == "image":
                pages.append(PageRef(item_index=idx, pdf_page_index=None, is_blank=False))
            elif it.kind == "pdf":
                doc = pdf_cache.get(it.path)
                if doc is None:
                    doc = open_pdf_checked(it.path)
                    pdf_cache[it.path] = doc
                for pno in range(doc.page_count):
                    pages.append(PageRef(item_index=idx, pdf_page_index=pno, is_blank=False))
            else:
                raise UserFacingError(f"未知のItem.kind: {it.kind}")
    finally:
        for d in pdf_cache.values():
            try:
                d.close()
            except Exception:
                pass
    return pages

def _prepare_image_for_jpeg(pil_img: Image.Image) -> Image.Image:
    if pil_img.mode == "RGB":
        return pil_img
    # PNGなどの透過を持つ画像は白背景で合成してJPEG化
    if pil_img.mode == "P":
        pil_img = pil_img.convert("RGBA")
    if pil_img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", pil_img.size, (255, 255, 255))
        bg.paste(pil_img, mask=pil_img.split()[-1])
        return bg
    return pil_img.convert("RGB")

def _insert_pil_image(page_out: fitz.Page, pil_img: Image.Image, rect: fitz.Rect, *, jpeg_quality: int) -> None:
    buf = io.BytesIO()
    img = _prepare_image_for_jpeg(pil_img)
    img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    page_out.insert_image(rect, stream=buf.getvalue())

def _fit_rect_pts(img_w: int, img_h: int, box_w: float, box_h: float):
    if img_w <= 0 or img_h <= 0:
        return (0.0, 0.0, box_w, box_h)
    scale = min(box_w / img_w, box_h / img_h)
    w = img_w * scale
    h = img_h * scale
    x = (box_w - w) / 2
    y = (box_h - h) / 2
    return (x, y, w, h)

def generate_pdf(
    items: list[Item],
    options: Options,
    output_pdf: str,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    cancel_cb: Optional[Callable[[], bool]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
) -> None:
    pages = build_logical_pages(items)

    if options.mode == "booklet":
        spreads = make_booklet_spreads(pages)
    else:
        spreads = make_two_up_spreads_for_output(pages, options.cover_preview)

    out_dir = os.path.dirname(os.path.abspath(output_pdf)) or os.getcwd()
    os.makedirs(out_dir, exist_ok=True)
    tmp_path = os.path.join(out_dir, f".tmp_{os.path.basename(output_pdf)}")

    dpi = options.dpi_compress if options.compress else options.dpi_normal
    jpegq = options.jpegq_compress if options.compress else options.jpegq_normal

    pdf_cache: Dict[str, fitz.Document] = {}
    doc_out = fitz.open()
    total = len(spreads)

    def _log(msg: str):
        if log_cb:
            log_cb(msg)

    try:
        for i, sp in enumerate(spreads, start=1):
            if cancel_cb and cancel_cb():
                raise UserFacingError("中断しました。")

            page_out = doc_out.new_page(width=A4_LANDSCAPE_W_PT, height=A4_LANDSCAPE_H_PT)
            half_w = A4_LANDSCAPE_W_PT / 2
            H = A4_LANDSCAPE_H_PT

            left_img = render_page_to_pil(items, sp.left, dpi=dpi, grayscale=options.grayscale, pdf_cache=pdf_cache)
            lx, ly, lw, lh = _fit_rect_pts(left_img.width, left_img.height, half_w, H)
            _insert_pil_image(page_out, left_img, fitz.Rect(lx, ly, lx+lw, ly+lh), jpeg_quality=jpegq)

            right_img = render_page_to_pil(items, sp.right, dpi=dpi, grayscale=options.grayscale, pdf_cache=pdf_cache)
            rx0 = half_w
            rx, ry, rw, rh = _fit_rect_pts(right_img.width, right_img.height, half_w, H)
            _insert_pil_image(page_out, right_img, fitz.Rect(rx0+rx, ry, rx0+rx+rw, ry+rh), jpeg_quality=jpegq)

            if progress_cb:
                progress_cb(i, total)
            if i == 1 or i == total or i % 10 == 0:
                _log(f"{i}/{total} ページ（出力スプレッド）を処理しました")

        doc_out.save(tmp_path)
    except UserFacingError:
        raise
    except Exception as e:
        raise UserFacingError(f"生成中にエラーが発生しました: {e}")
    finally:
        doc_out.close()
        for d in pdf_cache.values():
            try:
                d.close()
            except Exception:
                pass
    shutil.move(tmp_path, output_pdf)

def run_job_from_manifest(manifest_path: str) -> None:
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = validate_and_build_items(data["items"])
    opt = data.get("options", {})

    options = Options(
        mode=opt.get("mode", "booklet"),
        cover_preview=opt.get("cover_preview", True),
        grayscale=opt.get("grayscale", False),
        compress=opt.get("compress", False),
    )
    output_pdf = data["output_pdf"]
    generate_pdf(items, options, output_pdf)
