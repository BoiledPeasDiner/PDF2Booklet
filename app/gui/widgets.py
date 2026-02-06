from __future__ import annotations
import os
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QListWidget
from PySide6.QtGui import QDropEvent

class DropListWidget(QListWidget):
    """外部からのファイルD&Dを受け取り、(paths, insert_index) を通知する。"""
    files_dropped = Signal(list, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if not event.mimeData().hasUrls():
            return super().dropEvent(event)

        pos = event.position().toPoint()
        row = self.indexAt(pos).row()
        if row < 0:
            row = self.count()  # append

        paths = []
        for u in event.mimeData().urls():
            p = u.toLocalFile()
            if p and os.path.isfile(p):
                paths.append(p)

        self.files_dropped.emit(paths, row)
        event.acceptProposedAction()
