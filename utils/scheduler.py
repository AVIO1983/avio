from __future__ import annotations

import threading
import time
from datetime import datetime


class DailyTaskScheduler:
    def __init__(self, callback, hour: int = 23, minute: int = 55):
        self.callback = callback
        self.hour = hour
        self.minute = minute
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            now = datetime.now()
            if now.hour == self.hour and now.minute == self.minute:
                self.callback()
                time.sleep(65)
            time.sleep(20)
