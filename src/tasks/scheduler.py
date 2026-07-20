"""Background tasks scheduler (APScheduler)."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.db.mongodb import db_client
from src.memory.semantic_memory import SemanticMemory

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def consolidation_job() -> None:
    """
    Background consolidation job (runs periodically).
    Minimal Scope: Promote high-importance Working Memory to Semantic Memory,
    then run SemanticMemory.consolidate() for cleanup/deduplication.
    """
    logger.info("Starting memory consolidation job...")
    if db_client.db is None:
        logger.warning("DB not connected, skipping consolidation.")
        return

    try:
        # 1. Get all distinct users currently in Working Memory
        users = await db_client.db["working_memory"].distinct("user_id")

        for user_id in users:
            logger.info(f"Consolidating memory for user {user_id}")
            # wm = WorkingMemory(user_id=user_id)  # currently unused directly, but loaded for context
            sm = SemanticMemory(user_id=user_id)

            # 2. Promote Working -> Semantic (Minimal Scope)
            # Find working memory items with importance >= 0.7
            high_importance_cursor = db_client.db["working_memory"].find(
                {"user_id": user_id, "importance_score": {"$gte": 0.7}}
            )

            async for item in high_importance_cursor:
                # Add to Semantic Memory
                try:
                    await sm.add_fact(
                        fact=item["content"], importance=item["importance_score"]
                    )
                    # Remove from Working Memory once promoted
                    await db_client.db["working_memory"].delete_one(
                        {"_id": item["_id"]}
                    )
                    logger.debug(f"Promoted WM item {item['_id']} to Semantic Memory.")
                except Exception as e:
                    logger.error(f"Failed to promote WM item {item['_id']}: {e}")

            # 3. Trigger Semantic Memory's internal consolidation
            await sm.consolidate()

    except Exception as e:
        logger.error(f"Error during memory consolidation: {e}")


def start_scheduler() -> None:
    """Start the background scheduler."""
    scheduler.add_job(consolidation_job, "interval", minutes=60)
    scheduler.start()
    logger.info("APScheduler started (consolidation runs every 60m).")


def stop_scheduler() -> None:
    """Stop the background scheduler."""
    scheduler.shutdown()
    logger.info("APScheduler stopped.")
