from __future__ import annotations
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal, Slot

from app.core.types import Item, Options
from app.core.engine import generate_pdf
from app.core.errors import UserFacingError

@dataclass
class Job:
    items: list[Item]
    options: Options
    output_pdf: str

class Worker(QObject):
    progress = Signal(int, int)
    log = Signal(str)
    finished = Signal(str)
    failed = Signal(str)
    canceled = Signal(str)

    def __init__(self, job: Job):
        super().__init__()
        self.job = job
        self._cancel = False

    @Slot()
    def run(self):
        def cancel_cb() -> bool:
            return self._cancel

        def progress_cb(cur: int, total: int):
            self.progress.emit(cur, total)

        def log_cb(msg: str):
            self.log.emit(msg)

        try:
            generate_pdf(
                self.job.items,
                self.job.options,
                self.job.output_pdf,
                progress_cb=progress_cb,
                cancel_cb=cancel_cb,
                log_cb=log_cb,
            )
            self.finished.emit(self.job.output_pdf)
        except UserFacingError as e:
            if str(e).strip() == "中断しました。":
                self.canceled.emit("中断しました。")
            else:
                self.failed.emit(str(e))
        except Exception as e:
            self.failed.emit(f"不明なエラー: {e}")

    def cancel(self):
        self._cancel = True
