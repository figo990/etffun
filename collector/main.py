import threading
import signal
from .scheduler import build_scheduler, trigger_poll_loop


def main():
    import sys
    print("=" * 50)
    print("  ETF 数据采集器")
    print("=" * 50, flush=True)

    scheduler = build_scheduler()
    scheduler.start()
    print("[main] Scheduler started, registered tasks:", flush=True)

    t = threading.Thread(target=trigger_poll_loop, args=(scheduler,), daemon=True)
    t.start()
    print("[main] Trigger poll loop started", flush=True)

    scheduler.print_jobs()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    while not stop.is_set():
        try:
            stop.wait(5)
        except KeyboardInterrupt:
            stop.set()

    print("[main] Shutting down...", flush=True)
    scheduler.shutdown()


if __name__ == '__main__':
    main()
