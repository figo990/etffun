import threading
from .scheduler import build_scheduler, trigger_poll_loop


def main():
    import sys
    print("=" * 50)
    print("  ETF 数据采集器")
    print("=" * 50)

    scheduler = build_scheduler()
    scheduler.start()
    print("[main] Scheduler started, registered tasks:")

    # Start trigger polling in background
    t = threading.Thread(target=trigger_poll_loop, args=(scheduler,), daemon=True)
    t.start()
    print("[main] Trigger poll loop started")

    try:
        scheduler.print_jobs()
        # Keep main thread alive
        threading.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        print("[main] Shutting down...")
        scheduler.shutdown()


if __name__ == '__main__':
    main()
