# src/scheduler.py
from __future__ import annotations

import threading
import time
import traceback
from datetime import timedelta
from typing import Callable


def schedule_task(func: Callable[[], None], interval: timedelta) -> threading.Thread:
    """
    Run `func()` now and every `interval` seconds in a daemon thread.
    Any exception raised by `func` is printed (not swallowed) so you
    can debug background errors.
    """

    def _loop() -> None:
        # immediate run
        try:
            func()
        except Exception:
            traceback.print_exc()

        secs = interval.total_seconds()
        while True:
            time.sleep(secs)
            try:
                func()
            except Exception:
                traceback.print_exc()

    th = threading.Thread(target=_loop, daemon=True)
    th.start()
    return th
