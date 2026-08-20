"""Background tasks scheduler (APScheduler)."""

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.config import get_settings
from src.db.mongodb import db_client
from src.memory.semantic_memory import SemanticMemory
from src.services.embeddings.openai import OpenAIEmbeddingsAdapter
from src.skills.reminders.repository import claim_due_reminders

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def consolidation_job() -> None:
    """Promote high-importance Working Memory items and clean Semantic Memory.

    Runs periodically (default every 60 minutes). For each user that has
    Working Memory entries:

    1. Promote items with importance >= 0.7 into Semantic Memory.
    2. Run ``SemanticMemory.consolidate()`` (cleanup + deduplication).
    """
    logger.info("Starting memory consolidation job...")
    if db_client.db is None:
        logger.warning("DB not connected, skipping consolidation.")
        return

    working_coll = db_client.db["working_memory"]
    semantic_coll = db_client.db["semantic_memory"]

    embeddings = None
    settings = get_settings()
    if settings.openai_api_key:
        embeddings = OpenAIEmbeddingsAdapter()

    try:
        # Users with working-memory *or* semantic facts (the latter still
        # need cleanup/dedup even when WM is empty).
        wm_users = await working_coll.distinct("user_id")
        sm_users = await semantic_coll.distinct("user_id")
        users = list(dict.fromkeys([*wm_users, *sm_users]))

        for user_id in users:
            try:
                logger.info("Consolidating memory for user %s", user_id)
                sm = SemanticMemory(
                    user_id=user_id,
                    collection=semantic_coll,
                    embeddings_adapter=embeddings,
                )

                high_importance_cursor = working_coll.find(
                    {"user_id": user_id, "importance_score": {"$gte": 0.7}}
                )

                async for item in high_importance_cursor:
                    try:
                        await sm.add_fact(
                            fact=item["content"], importance=item["importance_score"]
                        )
                        await working_coll.delete_one({"_id": item["_id"]})
                        logger.debug(
                            "Promoted WM item %s to Semantic Memory.", item["_id"]
                        )
                    except Exception as e:
                        logger.error("Failed to promote WM item %s: %s", item["_id"], e)

                await sm.consolidate()
            except Exception as e:
                logger.error("Consolidation failed for user %s: %s", user_id, e)

    except Exception as e:
        logger.error("Error during memory consolidation: %s", e)


async def due_reminder_job() -> None:
    """Mark pending reminders as fired when due_at has passed.

    Delivery to the open tab is the frontend poll of GET /reminders/due.
    This job only claims so fired_at is set even if no client is polling.
    """
    if db_client.db is None:
        logger.warning("DB not connected, skipping due reminders.")
        return
    try:
        claimed = await claim_due_reminders(
            db_client.db["reminders"], datetime.now(UTC)
        )
        if claimed:
            logger.info("Claimed %s due reminder(s)", len(claimed))
    except Exception:
        logger.exception("Due reminder job failed")


def start_scheduler() -> None:
    """Start the background scheduler (idempotent).

    Registers the consolidation job (every 60 minutes) and starts the
    scheduler. Subsequent calls are no-ops if already running.
    """
    if scheduler.running:
        return
    scheduler.add_job(
        consolidation_job,
        "interval",
        minutes=60,
        id="memory_consolidation",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        due_reminder_job,
        "interval",
        seconds=30,
        id="due_reminders",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("APScheduler started (consolidation 60m, due reminders 30s).")


def stop_scheduler() -> None:
    """Stop the background scheduler (idempotent).

    No-op if the scheduler is not running. Waits for an in-flight
    consolidation job so Mongo is not closed under it.
    """
    if not scheduler.running:
        return
    scheduler.shutdown(wait=True)
    logger.info("APScheduler stopped.")
