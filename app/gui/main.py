from __future__ import annotations
import os
from typing import List

from PySide6.QtCore import Qt, QSettings, QThread, QPointF, QRectF
from PySide6.QtGui import QPixmap, QImage, QIcon, QPainter, QColor, QPen, QPainterPath
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QFileDialog, QLabel, QPlainTextEdit, QMessageBox, QScrollArea,
    QRadioButton, QButtonGroup, QCheckBox, QProgressBar, QSplitter,
    QAbstractItemView, QSizePolicy
)

from app.core.types import Item, Options
from app.core.errors import UserFacingError, is_heic, is_supported_image, is_pdf
from app.core.engine import build_logical_pages, validate_and_build_items
from app.core.plan import make_preview_spreads
from app.core.render import render_spread_preview, A4_LANDSCAPE_IN

# 解決：相対importを絶対importに変更
# from .widgets import DropListWidget
# from .worker import Worker, Job
from app.gui.widgets import DropListWidget
from app.gui.worker import Worker, Job

APP_TITLE = "PDF2Booklet"
ORG_NAME = "PDF2Booklet"
APP_NAME = "PDF2Booklet"

def pil_to_qpixmap(pil_img) -> QPixmap:
    rgb = pil_img.convert("RGB")
    w, h = rgb.size
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(data, w, h, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)

class PreviewWidget(QWidget):
    def __init__(self, width: int, height: int):
        super().__init__()
        self.setFixedSize(width, height)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._pixmap: QPixmap | None = None
        self._message = "隱ｭ縺ｿ霎ｼ縺ｿ荳ｭ窶ｦ"
        self._message_color = QColor("#777")
        self._bg_color = QColor("#1a1a1a")
        self._lens_enabled = False
        self._lens_center = QPointF(width / 2, height / 2)
        self._lens_radius = 120.0
        self._lens_zoom = 2.0
        self._dragging = False

    def set_pixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self._message = ""
        self.update()

    def set_message(self, msg: str, color: str = "#777"):
        self._pixmap = None
        self._message = msg
        self._message_color = QColor(color)
        self._lens_enabled = False
        self._dragging = False
        self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap:
            self._lens_enabled = not self._lens_enabled
            if self._lens_enabled:
                self._lens_center = QPointF(event.position())
            else:
                self._dragging = False
            self.update()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._lens_enabled:
            self._dragging = True
            self._lens_center = QPointF(event.position())
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._lens_enabled and self._dragging:
            self._lens_center = QPointF(event.position())
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            if self._lens_enabled:
                self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._bg_color)
        if self._pixmap:
            painter.drawPixmap(self.rect(), self._pixmap)
        else:
            painter.setPen(self._message_color)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._message)
            return

        if self._lens_enabled and self._dragging:
            self._paint_lens(painter)

    def _paint_lens(self, painter: QPainter):
        if not self._pixmap:
            return
        center = self._lens_center
        radius = self._lens_radius
        lens_rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        if not lens_rect.intersects(QRectF(self.rect())):
            return

        src_radius = radius / self._lens_zoom
        src_rect = QRectF(center.x() - src_radius, center.y() - src_radius, src_radius * 2, src_radius * 2)

        scale_x = self._pixmap.width() / max(1, self.width())
        scale_y = self._pixmap.height() / max(1, self.height())
        src_rect = QRectF(
            src_rect.x() * scale_x,
            src_rect.y() * scale_y,
            src_rect.width() * scale_x,
            src_rect.height() * scale_y,
        )
        src_rect = src_rect.intersected(QRectF(0, 0, self._pixmap.width(), self._pixmap.height()))

        painter.save()
        clip_path = QPainterPath()
        clip_path.addEllipse(lens_rect)
        painter.setClipPath(clip_path)
        painter.drawPixmap(lens_rect, self._pixmap, src_rect)
        painter.restore()

        shadow_pen = QPen(QColor(0, 0, 0, 140), 4)
        painter.setPen(shadow_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(lens_rect)

        border_pen = QPen(QColor(255, 255, 255, 220), 2)
        painter.setPen(border_pen)
        painter.drawEllipse(lens_rect)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)

        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "icon.ico")
        icon_path = os.path.abspath(icon_path)
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.items: List[Item] = []
        self.preview_spreads = []
        self.preview_labels: List[PreviewWidget] = []
        self._preview_item_height = 0
        self._preview_item_width = 0
        self._preview_dpi = 110
        self._preview_rendered: List[bool] = []
        self._suspend_scroll_handler = False
        self.last_output_pdf = ""

        self._thread: QThread | None = None
        self._worker: Worker | None = None

        self._build_ui()
        self._load_settings()
        self._refresh_list()
        self._rebuild_preview()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        # Left pane
        left = QWidget()
        left_layout = QVBoxLayout(left)

        self.listw = DropListWidget()
        self.listw.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.listw.files_dropped.connect(self.on_files_dropped)
        self.listw.items_reordered.connect(self.on_list_reordered)
        self.listw.delete_requested.connect(self.on_delete_clicked)
        left_layout.addWidget(self.listw, stretch=1)

        btn_row1 = QHBoxLayout()
        self.btn_add = QPushButton("追加…")
        self.btn_del = QPushButton("削除")
        btn_row1.addWidget(self.btn_add)
        btn_row1.addWidget(self.btn_del)
        left_layout.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        self.btn_up = QPushButton("上へ")
        self.btn_down = QPushButton("下へ")
        btn_row2.addWidget(self.btn_up)
        btn_row2.addWidget(self.btn_down)
        left_layout.addLayout(btn_row2)

        btn_row3 = QHBoxLayout()
        self.btn_sort = QPushButton("名前でソート")
        self.btn_blank = QPushButton("空白を後ろに挿入")
        btn_row3.addWidget(self.btn_sort)
        btn_row3.addWidget(self.btn_blank)
        left_layout.addLayout(btn_row3)

        self.lbl_sort_note = QLabel("※ ソートは最初の整列用途を想定（空白も含めて移動します）")
        self.lbl_sort_note.setWordWrap(True)
        self.lbl_sort_note.setStyleSheet("color: #666;")
        left_layout.addWidget(self.lbl_sort_note)

        splitter.addWidget(left)

        # Center pane
        center = QWidget()
        center_layout = QVBoxLayout(center)

        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_container = QWidget()
        self.preview_container.setStyleSheet("background: #111;")
        self.preview_layout = QVBoxLayout(self.preview_container)
        self.preview_layout.setContentsMargins(16, 16, 16, 16)
        self.preview_layout.setSpacing(16)
        self.preview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.preview_scroll.setWidget(self.preview_container)
        center_layout.addWidget(self.preview_scroll, stretch=1)

        nav = QHBoxLayout()
        self.lbl_spread = QLabel("見開き 0 / 0")
        nav.addStretch(1)
        nav.addWidget(self.lbl_spread)
        center_layout.addLayout(nav)

        splitter.addWidget(center)

        # Right pane
        right = QWidget()
        right_layout = QVBoxLayout(right)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([300, 600, 300])

        # Bottom controls
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        right_layout.addWidget(bottom)

        mode_row = QHBoxLayout()
        self.rb_booklet = QRadioButton("ブックレット（デフォルト）")
        self.rb_two = QRadioButton("2-in-1（通常順）")
        self.rb_booklet.setChecked(True)
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.rb_booklet)
        self.mode_group.addButton(self.rb_two)
        mode_row.addWidget(self.rb_booklet)
        mode_row.addWidget(self.rb_two)
        mode_row.addStretch(1)
        bottom_layout.addLayout(mode_row)

        opt_row = QHBoxLayout()
        self.cb_cover = QCheckBox("表紙（プレビュー/2-in-1のみ）")
        self.cb_cover.setChecked(True)
        self.cb_gray = QCheckBox("グレースケール")
        self.cb_gray.setChecked(False)
        self.cb_comp = QCheckBox("省サイズ（高画質）")
        self.cb_comp.setChecked(False)
        opt_row.addWidget(self.cb_cover)
        opt_row.addWidget(self.cb_gray)
        opt_row.addWidget(self.cb_comp)
        opt_row.addStretch(1)
        bottom_layout.addLayout(opt_row)

        self.lbl_cover_note = QLabel("※ ブックレット出力では表紙オプションは反映されません（プレビュー/2-in-1のみ）")
        self.lbl_cover_note.setWordWrap(True)
        self.lbl_cover_note.setStyleSheet("color: #666;")
        bottom_layout.addWidget(self.lbl_cover_note)

        action_row = QHBoxLayout()
        self.btn_generate = QPushButton("PDF生成…")
        self.btn_cancel = QPushButton("中断")
        self.btn_open_folder = QPushButton("保存先を開く")
        self.btn_open_folder.setEnabled(False)
        action_row.addWidget(self.btn_generate)
        action_row.addWidget(self.btn_cancel)
        action_row.addWidget(self.btn_open_folder)
        action_row.addStretch(1)
        bottom_layout.addLayout(action_row)

        self.pbar = QProgressBar()
        self.pbar.setValue(0)
        bottom_layout.addWidget(self.pbar)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        bottom_layout.addWidget(self.log)

        # signals
        self.btn_add.clicked.connect(self.on_add_clicked)
        self.btn_del.clicked.connect(self.on_delete_clicked)
        self.btn_up.clicked.connect(lambda: self.on_move(-1))
        self.btn_down.clicked.connect(lambda: self.on_move(+1))
        self.btn_sort.clicked.connect(self.on_sort_clicked)
        self.btn_blank.clicked.connect(self.on_insert_blank)
        self.preview_scroll.verticalScrollBar().valueChanged.connect(self.on_preview_scrolled)
        self.cb_cover.stateChanged.connect(lambda _: self._rebuild_preview())
        self.cb_gray.stateChanged.connect(lambda _: self._rebuild_preview())
        self.rb_booklet.toggled.connect(self.on_mode_changed)
        self.btn_generate.clicked.connect(self.on_generate_clicked)
        self.btn_cancel.clicked.connect(self.on_cancel_clicked)
        self.btn_open_folder.clicked.connect(self.on_open_folder_clicked)

        self.lbl_cover_note.setVisible(True)

    def _load_settings(self):
        last_dir = self.settings.value("last_output_dir", "")
        self._last_output_dir = last_dir if isinstance(last_dir, str) else ""

    def _save_settings(self):
        if getattr(self, "_last_output_dir", ""):
            self.settings.setValue("last_output_dir", self._last_output_dir)

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)

    def _refresh_list(self):
        self.listw.clear()
        for it in self.items:
            self.listw.addItem("(空白)" if it.kind == "blank" else it.display_name)

        self._attach_item_data()

    def _attach_item_data(self):
        for i in range(self.listw.count()):
            widget_item = self.listw.item(i)
            if i < len(self.items):
                widget_item.setData(Qt.ItemDataRole.UserRole, self.items[i])

    def _sync_items_from_list(self):
        new_items: List[Item] = []
        for i in range(self.listw.count()):
            widget_item = self.listw.item(i)
            data = widget_item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, Item):
                new_items.append(data)
            elif i < len(self.items):
                new_items.append(self.items[i])
        self.items = new_items

    def on_list_reordered(self):
        self._sync_items_from_list()
        self._rebuild_preview()

    def _append_log(self, msg: str):
        self.log.appendPlainText(msg)

    def _error(self, title: str, msg: str):
        self._append_log(f"[ERROR] {msg}")
        QMessageBox.critical(self, title, msg)

    def _warn(self, title: str, msg: str):
        self._append_log(f"[WARN] {msg}")
        QMessageBox.warning(self, title, msg)

    def _classify_paths(self, paths: List[str]) -> List[Item]:
        raw = []
        for p in paths:
            if is_heic(p):
                raise UserFacingError("HEIC(.heic/.heif) は未対応です。JPG/PNGに変換してから追加してください。")
            if is_pdf(p):
                raw.append({"kind":"pdf","path":p})
            elif is_supported_image(p):
                raw.append({"kind":"image","path":p})
            else:
                raise UserFacingError(f"未対応のファイル形式です: {p}")
        return validate_and_build_items(raw)

    def on_files_dropped(self, paths: List[str], insert_row: int):
        if not paths:
            return
        paths = sorted(paths, key=lambda x: os.path.basename(x))  # 仕様：ドロップ複数は名前でソート
        try:
            new_items = self._classify_paths(paths)
        except UserFacingError as e:
            self._error("追加できません", str(e))
            return

        insert_row = max(0, min(insert_row, len(self.items)))
        self.items[insert_row:insert_row] = new_items
        self._refresh_list()
        self._rebuild_preview()

    def on_add_clicked(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "ファイルを追加", "",
            "PDF/Images (*.pdf *.png *.jpg *.jpeg);;All files (*.*)"
        )
        if not paths:
            return
        paths = sorted(paths, key=lambda x: os.path.basename(x))
        try:
            new_items = self._classify_paths(paths)
        except UserFacingError as e:
            self._error("追加できません", str(e))
            return
        self.items.extend(new_items)
        self._refresh_list()
        self._rebuild_preview()

    def on_delete_clicked(self):
        rows = sorted({i.row() for i in self.listw.selectedIndexes()}, reverse=True)
        if not rows:
            return
        if len(rows) > 1:
            resp = QMessageBox.question(
                self,
                "Delete",
                f"Delete {len(rows)} items?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if resp != QMessageBox.StandardButton.Yes:
                return
        for r in rows:
            if 0 <= r < len(self.items):
                self.items.pop(r)
        self._refresh_list()
        self._rebuild_preview()

    def on_move(self, delta: int):
        rows = sorted({i.row() for i in self.listw.selectedIndexes()})
        if len(rows) != 1:
            self._warn("移動", "移動は1件選択のときに使用してください。")
            return
        r = rows[0]
        nr = r + delta
        if not (0 <= nr < len(self.items)):
            return
        self.items[r], self.items[nr] = self.items[nr], self.items[r]
        self._refresh_list()
        self.listw.setCurrentRow(nr)
        self._rebuild_preview()

    def on_sort_clicked(self):
        self.items.sort(key=lambda it: it.display_name)
        self._refresh_list()
        self._rebuild_preview()

    def on_insert_blank(self):
        rows = sorted({i.row() for i in self.listw.selectedIndexes()})
        if len(rows) != 1:
            self._warn("空白挿入", "空白挿入は1件選択のときに使用してください。")
            return
        r = rows[0]
        self.items.insert(r + 1, Item(kind="blank", path=None, display_name="(空白)"))
        self._refresh_list()
        self._rebuild_preview()

    def on_mode_changed(self):
        self.lbl_cover_note.setVisible(self.rb_booklet.isChecked())

    def _rebuild_preview(self):
        self.preview_spreads = []
        try:
            pages = build_logical_pages(self.items)
            self.preview_spreads = make_preview_spreads(pages, self.cb_cover.isChecked())
        except UserFacingError as e:
            self._append_log(f"[ERROR] {e}")
            self._set_preview_message("プレビュー生成エラー")
            return
        self._build_preview_placeholders(keep_position=False)

    def _clear_preview_layout(self):
        while self.preview_layout.count():
            item = self.preview_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.preview_labels = []
        self._preview_item_height = 0
        self._preview_item_width = 0
        self._preview_rendered = []

    def _set_preview_message(self, msg: str):
        self._clear_preview_layout()
        label = QLabel(msg)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #ddd;")
        self.preview_layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.lbl_spread.setText("見開き 0 / 0")

    def _preview_target_width(self) -> int:
        viewport = self.preview_scroll.viewport()
        width = viewport.width()
        if width <= 10:
            width = self.preview_scroll.width()
        if width <= 10:
            width = 520
        left, top, right, bottom = self.preview_layout.getContentsMargins()
        return max(200, width - left - right)

    def _calc_preview_dpi(self) -> int:
        base_width = self._preview_target_width()
        dpi = int(base_width / A4_LANDSCAPE_IN[0])
        return max(30, dpi)

    def _current_spread_index(self) -> int:
        total = len(self.preview_spreads)
        if total == 0 or self._preview_item_height <= 0:
            return 0
        vsb = self.preview_scroll.verticalScrollBar()
        top_margin = self.preview_layout.contentsMargins().top()
        spacing = self.preview_layout.spacing()
        step = max(1, self._preview_item_height + spacing)
        pos = max(0, vsb.value() - top_margin)
        return min(total - 1, pos // step)

    def _scroll_to_index(self, index: int):
        total = len(self.preview_spreads)
        if total == 0 or self._preview_item_height <= 0:
            return
        index = max(0, min(index, total - 1))
        top_margin = self.preview_layout.contentsMargins().top()
        spacing = self.preview_layout.spacing()
        step = max(1, self._preview_item_height + spacing)
        self.preview_scroll.verticalScrollBar().setValue(int(top_margin + index * step))

    def _update_spread_label(self):
        total = len(self.preview_spreads)
        if total == 0:
            self.lbl_spread.setText("見開き 0 / 0")
            return
        index = self._current_spread_index()
        self.lbl_spread.setText(f"見開き {index + 1} / {total}")

    def on_preview_scrolled(self, _value: int):
        if self._suspend_scroll_handler:
            return
        self._update_spread_label()
        self._render_visible_previews()

    def _build_preview_placeholders(self, keep_position: bool = True):
        total = len(self.preview_spreads)
        if total == 0:
            self._set_preview_message("プレビューなし")
            return

        current_index = self._current_spread_index() if keep_position else 0
        self._suspend_scroll_handler = True
        self._clear_preview_layout()
        dpi = self._calc_preview_dpi()
        self._preview_dpi = dpi
        self._preview_item_width = int(A4_LANDSCAPE_IN[0] * dpi)
        self._preview_item_height = int(A4_LANDSCAPE_IN[1] * dpi)
        self._preview_rendered = [False] * total
        for _ in self.preview_spreads:
            preview = PreviewWidget(self._preview_item_width, self._preview_item_height)
            self.preview_layout.addWidget(preview, alignment=Qt.AlignmentFlag.AlignHCenter)
            self.preview_labels.append(preview)
        self._scroll_to_index(current_index)
        self._update_spread_label()
        self._suspend_scroll_handler = False
        self._render_visible_previews()

    def _render_visible_previews(self):
        total = len(self.preview_spreads)
        if total == 0 or self._preview_item_height <= 0:
            return
        vsb = self.preview_scroll.verticalScrollBar()
        top_margin = self.preview_layout.contentsMargins().top()
        spacing = self.preview_layout.spacing()
        step = max(1, self._preview_item_height + spacing)
        viewport_h = self.preview_scroll.viewport().height()
        top = max(0, vsb.value() - top_margin)
        bottom = top + viewport_h
        buffer = 1
        start = max(0, (top // step) - buffer)
        end = min(total - 1, (bottom // step) + buffer)
        for idx in range(start, end + 1):
            if self._preview_rendered[idx]:
                continue
            try:
                pil = render_spread_preview(
                    self.items,
                    self.preview_spreads[idx],
                    dpi=self._preview_dpi,
                    grayscale=self.cb_gray.isChecked(),
                )
                pix = pil_to_qpixmap(pil)
                widget = self.preview_labels[idx]
                widget.set_pixmap(pix)
            except UserFacingError as e:
                self._append_log(f"[ERROR] {e}")
                widget = self.preview_labels[idx]
                widget.set_message("??????", color="#ffb4a2")
            self._preview_rendered[idx] = True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.preview_spreads:
            self._build_preview_placeholders(keep_position=True)

    def on_generate_clicked(self):
        if not self.items:
            self._warn("生成", "入力ファイルがありません。")
            return

        default_dir = getattr(self, "_last_output_dir", "") or os.getcwd()
        out_path, _ = QFileDialog.getSaveFileName(
            self, "出力PDFを保存", os.path.join(default_dir, "output.pdf"), "PDF (*.pdf)"
        )
        if not out_path:
            return
        if not out_path.lower().endswith(".pdf"):
            out_path += ".pdf"

        self._last_output_dir = os.path.dirname(out_path)

        mode = "booklet" if self.rb_booklet.isChecked() else "two_up"
        cover_for_output = self.cb_cover.isChecked() if mode == "two_up" else False

        opts = Options(
            mode=mode,
            cover_preview=cover_for_output,
            grayscale=self.cb_gray.isChecked(),
            compress=self.cb_comp.isChecked(),
        )

        self.pbar.setValue(0)
        self.btn_generate.setEnabled(False)
        self.btn_open_folder.setEnabled(False)
        self._append_log(f"[INFO] 生成開始: mode={mode}, grayscale={opts.grayscale}, compress={opts.compress}")

        job = Job(items=list(self.items), options=opts, output_pdf=out_path)
        self._thread = QThread(self)
        self._worker = Worker(job)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.on_job_progress)
        self._worker.log.connect(lambda m: self._append_log(f"[JOB] {m}"))
        self._worker.finished.connect(self.on_job_finished)
        self._worker.failed.connect(self.on_job_failed)
        self._worker.canceled.connect(self.on_job_canceled)

        def cleanup():
            if self._thread:
                self._thread.quit()
                self._thread.wait(2000)
            self._thread = None
            self._worker = None
            self.btn_generate.setEnabled(True)

        self._worker.finished.connect(lambda _: cleanup())
        self._worker.failed.connect(lambda _: cleanup())
        self._worker.canceled.connect(lambda _: cleanup())

        self._thread.start()

    def on_job_progress(self, cur: int, total: int):
        if total <= 0:
            self.pbar.setValue(0)
            return
        self.pbar.setMaximum(total)
        self.pbar.setValue(cur)

    def on_job_finished(self, out_path: str):
        self._append_log(f"[INFO] 生成完了: {out_path}")
        self.last_output_pdf = out_path
        self.btn_open_folder.setEnabled(True)
        QMessageBox.information(self, "完了", "PDF生成が完了しました。")

    def on_job_failed(self, msg: str):
        self._error("生成エラー", msg)

    def on_job_canceled(self, msg: str):
        self._append_log(f"[INFO] {msg}")
        QMessageBox.information(self, "中断", msg)

    def on_cancel_clicked(self):
        if self._worker:
            self._append_log("[INFO] 中断要求")
            self._worker.cancel()

    def on_open_folder_clicked(self):
        if not self.last_output_pdf:
            return
        folder = os.path.dirname(os.path.abspath(self.last_output_pdf))
        try:
            os.startfile(folder)
        except Exception as e:
            self._warn("フォルダを開けません", str(e))


def main():
    app = QApplication()
    w = MainWindow()
    w.resize(1200, 760)
    w.show()
    app.exec()

if __name__ == "__main__":
    main()
