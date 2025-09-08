# tests/test_scheduler.py
import threading
import time
from datetime import timedelta
import pytest
from src.scheduler import schedule_task


def test_schedule_runs_function():
    calls = []

    def f():
        calls.append(time.time())

    # schedule f every 0.05s
    schedule_task(f, timedelta(seconds=0.05))
    time.sleep(0.16)  # allow ~3 runs
    assert len(calls) >= 3

    # background thread should be daemon
    threads = threading.enumerate()
    assert any(t.daemon for t in threads)


if __name__ == "__main__":
    pytest.main()
