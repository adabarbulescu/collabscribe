"""
Background snapshot scheduler for automatic document versioning.

Creates document snapshots on configurable time/operation thresholds:
- Snapshot every 5 minutes of active editing OR
- Snapshot after every 50 Yjs operations (whichever comes first)

Runs as async background task integrated with FastAPI lifespan.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from database import get_pool
from services import VersioningService, DocumentNotFoundError
from utils import get_tracking_manager, get_yjs_parser

logger = logging.getLogger(__name__)


class SnapshotScheduler:
    """
    Background scheduler that periodically creates document snapshots.
    
    Checks for documents exceeding operation/time thresholds and
    automatically creates versions using VersioningService.
    
    Runs as async background task during application lifetime.
    """

    def __init__(self, versioning_service: VersioningService, poll_interval: int = 60):
        """
        Initialize snapshot scheduler.

        Args:
            versioning_service: Injected VersioningService for version creation
            poll_interval: Seconds between threshold checks (default 60)
        """
        self.versioning_service = versioning_service
        self.poll_interval = poll_interval
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        self.tracking_manager = get_tracking_manager()
        self.yjs_parser = get_yjs_parser()

    async def start(self) -> None:
        """
        Start the snapshot scheduler background task.

        Creates async task that runs background polling.
        Safe to call multiple times (idempotent).
        """
        if self.is_running:
            logger.warning("Snapshot scheduler already running")
            return

        self.is_running = True
        self.task = asyncio.create_task(self._run_scheduler())
        logger.info(f"Snapshot scheduler started (poll interval: {self.poll_interval}s)")

    async def stop(self) -> None:
        """
        Stop the snapshot scheduler background task.

        Cancels polling and waits for task cleanup.
        Safe to call multiple times (idempotent).
        """
        if not self.is_running:
            return

        self.is_running = False
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        logger.info("Snapshot scheduler stopped")

    async def _run_scheduler(self) -> None:
        """
        Main scheduler loop (runs as background task).

        Continuously:
        1. Waits for poll interval
        2. Checks documents exceeding thresholds
        3. Creates snapshots for those documents
        4. Resets operation counters

        Runs until stop() is called or task cancelled.
        """
        while self.is_running:
            try:
                await asyncio.sleep(self.poll_interval)

                if not self.is_running:
                    break

                # Get documents needing snapshots
                docs_to_snapshot = (
                    self.tracking_manager.get_documents_needing_snapshot()
                )

                for doc_id in docs_to_snapshot:
                    await self._create_snapshot(doc_id)

            except asyncio.CancelledError:
                logger.debug("Snapshot scheduler cancelled")
                break
            except Exception as e:
                logger.error(
                    f"Error in snapshot scheduler loop: {e}",
                    exc_info=True,
                )
                # Continue running despite errors

    async def _create_snapshot(self, doc_id: str) -> None:
        """
        Create a snapshot version for a document.

        Retrieves current document content from Yjs parser,
        creates version via VersioningService, and resets
        operation counter.

        Args:
            doc_id: Document identifier to snapshot
        """
        try:
            # Get current document content from per-document Y.Doc
            content = self.yjs_parser.get_document_text(doc_id)

            if not content or not content.strip():
                logger.warning(
                    f"Skipping snapshot for {doc_id}: no content available from Yjs parser"
                )
                # Still reset the counter so we don't loop forever
                # on a document where the server-side Y.Doc has no content
                self.tracking_manager.mark_snapshot_created(doc_id)
                return

            # Create version
            version_id, version_num = await self.versioning_service.create_version(
                doc_id, content
            )

            logger.info(
                f"Auto-snapshot created for {doc_id}: "
                f"version {version_num} ({version_id})"
            )

            # Mark snapshot created to reset counters
            self.tracking_manager.mark_snapshot_created(doc_id)

            # Log current status
            status = self.tracking_manager.get_tracker_status(doc_id)
            if status:
                logger.debug(f"Document {doc_id} snapshot status reset: {status}")

        except DocumentNotFoundError:
            logger.warning(f"Document not found: {doc_id}")
            self.tracking_manager.clear_tracker(doc_id)
        except Exception as e:
            logger.error(
                f"Failed to create snapshot for {doc_id}: {e}",
                exc_info=True,
            )

    async def get_scheduler_status(self) -> dict:
        """
        Get current scheduler status and monitored documents.

        Returns:
            Dictionary with:
            - is_running: Whether scheduler is active
            - poll_interval: Seconds between checks
            - documents_tracked: Count of active documents
            - documents_needing_snapshot: Count exceeding thresholds
            - tracked_documents: Detailed status per document
        """
        docs_needing_snapshot = (
            self.tracking_manager.get_documents_needing_snapshot()
        )
        all_statuses = self.tracking_manager.get_all_tracker_statuses()

        return {
            "is_running": self.is_running,
            "poll_interval": self.poll_interval,
            "documents_tracked": len(all_statuses),
            "documents_needing_snapshot": len(docs_needing_snapshot),
            "documents_needing_snapshot_list": docs_needing_snapshot,
            "tracked_documents": all_statuses,
            "timestamp": datetime.now().isoformat(),
        }


# Global scheduler instance
_scheduler_instance: Optional[SnapshotScheduler] = None


async def get_snapshot_scheduler() -> SnapshotScheduler:
    """
    Get or create global snapshot scheduler instance.

    Ensures versioning service is available.

    Returns:
        Shared SnapshotScheduler instance
    """
    global _scheduler_instance

    if _scheduler_instance is None:
        pool = get_pool()
        versioning_service = VersioningService(pool)
        _scheduler_instance = SnapshotScheduler(versioning_service)

    return _scheduler_instance


@asynccontextmanager
async def snapshot_scheduler_lifespan():
    """
    Context manager for snapshot scheduler lifecycle.

    Automatically starts scheduler on entry,
    stops on exit (cleanup).

    Usage in FastAPI:
    @app.lifespan
    async def lifespan(app):
        async with snapshot_scheduler_lifespan():
            yield

    Yields on successful start, allowing app to run during context.
    """
    scheduler = await get_snapshot_scheduler()

    try:
        await scheduler.start()
        yield
    finally:
        await scheduler.stop()
