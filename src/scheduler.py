# src/scheduler.py

from datetime import timedelta
from typing import Callable
import threading
import time


def schedule_task(func: Callable[[], None], interval: timedelta) -> threading.Thread:
    """
    Schedule `func` to run immediately and then every `interval` in the background.
    Returns the daemon Thread that’s been started.
    """

    def _loop():
        # first call right away
        try:
            func()
        except Exception:
            pass

        # then run forever, sleeping between calls
        secs = interval.total_seconds()
        while True:
            time.sleep(secs)
            try:
                func()
            except Exception:
                pass

    th = threading.Thread(target=_loop, daemon=True)
    th.start()
    return th
