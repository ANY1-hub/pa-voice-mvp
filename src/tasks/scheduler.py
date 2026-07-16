from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

def dummy_consolidation_job():
    logger.info("Running memory consolidation job...")

def start_scheduler():
    # Schedule the memory consolidation job (e.g., every hour for testing)
    scheduler.add_job(dummy_consolidation_job, 'interval', minutes=60)
    scheduler.start()
    logger.info("Background task scheduler started.")

def stop_scheduler():
    scheduler.shutdown()
    logger.info("Background task scheduler stopped.")