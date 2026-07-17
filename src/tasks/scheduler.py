"""Background task scheduler (APScheduler) for memory consolidation etc."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def dummy_consolidation_job() -> None:
    """Placeholder job that will later run real memory consolidation."""
    logger.info("Running memory consolidation job...")


def start_scheduler() -> None:
    """Start the background scheduler and register jobs."""
    # Schedule the memory consolidation job (every hour for now)
    scheduler.add_job(dummy_consolidation_job, "interval", minutes=60)
    scheduler.start()
    logger.info("Background task scheduler started.")


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    scheduler.shutdown()
    logger.info("Background task scheduler stopped.")
