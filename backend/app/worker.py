"""Background worker — runs change_detector and session_indexer in a separate process."""
import asyncio
import signal

from .config import ES_URL
from .services import version_db, change_detector, blueprint_service


async def main():
    """Initialize services and run background scanning tasks."""
    await version_db.init_db()
    await blueprint_service.initialize_blueprint_dirs()
    await change_detector.start_detector(interval=30)

    indexer = None
    if ES_URL:
        from .services.session_indexer import SessionIndexer
        indexer = SessionIndexer()
        await indexer.start()

    # Block until SIGINT/SIGTERM
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    print("[worker] Background worker started")
    await stop.wait()

    # Graceful shutdown
    print("[worker] Shutting down...")
    if indexer:
        await indexer.stop()
    await change_detector.stop_detector()
    await version_db.close_db()


if __name__ == "__main__":
    asyncio.run(main())
