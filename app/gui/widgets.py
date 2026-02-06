from __future__ import annotations
import os
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QListWidget, QAbstractItemView
from PySide6.QtGui import QDropEvent

class DropListWidget(QListWidget):
    """外部からのファイルD&Dを受け取り、(paths, insert_index) を通知する。"""
    files_dropped = Signal(list, int)
    items_reordered = Signal()
    delete_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

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
            internal = event.source() is self
            super().dropEvent(event)
            if internal:
                self.items_reordered.emit()
            return

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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.delete_requested.emit()
            return
        super().keyPressEvent(event)
