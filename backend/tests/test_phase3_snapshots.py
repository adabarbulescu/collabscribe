"""
Unit tests for background snapshot scheduler.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from tasks import SnapshotScheduler
from utils import OperationTrackingManager


class TestSnapshotScheduler:
    @pytest.fixture
    def mock_versioning_service(self):
        service = AsyncMock()
        service.create_version = AsyncMock(return_value=("version-id-123", 1))
        return service

    @pytest.fixture
    def scheduler(self, mock_versioning_service):
        SnapshotScheduler(mock_versioning_service, poll_interval=1).tracking_manager._trackers.clear()
        scheduler = SnapshotScheduler(mock_versioning_service, poll_interval=1)
        scheduler.tracking_manager._trackers.clear()
        scheduler.yjs_parser.get_document_text = lambda doc_id: f"content for {doc_id}"
        return scheduler

    def test_scheduler_initialization(self, scheduler):
        assert not scheduler.is_running
        assert scheduler.poll_interval == 1
        assert scheduler.task is None

    @pytest.mark.asyncio
    async def test_scheduler_start(self, scheduler):
        await scheduler.start()
        assert scheduler.is_running
        assert scheduler.task is not None
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_start_idempotent(self, scheduler):
        await scheduler.start()
        task1 = scheduler.task
        await scheduler.start()
        assert task1 == scheduler.task
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_stop(self, scheduler):
        await scheduler.start()
        await scheduler.stop()
        assert not scheduler.is_running

    @pytest.mark.asyncio
    async def test_scheduler_stop_idempotent(self, scheduler):
        await scheduler.start()
        await scheduler.stop()
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_creates_snapshot_for_document(self, scheduler):
        doc_id = "test_doc"
        scheduler.tracking_manager.get_or_create_tracker(doc_id).operation_count = 50
        await scheduler._create_snapshot(doc_id)
        scheduler.versioning_service.create_version.assert_called_once()
        assert scheduler.tracking_manager.get_tracker_status(doc_id)["operations_since_snapshot"] == 0

    @pytest.mark.asyncio
    async def test_scheduler_handles_missing_document(self, scheduler):
        from services import DocumentNotFoundError

        scheduler.versioning_service.create_version = AsyncMock(
            side_effect=DocumentNotFoundError("Not found")
        )
        await scheduler._create_snapshot("nonexistent_doc")
        assert scheduler.tracking_manager.get_tracker_status("nonexistent_doc") is None

    @pytest.mark.asyncio
    async def test_scheduler_status(self, scheduler):
        await scheduler.start()
        scheduler.tracking_manager.record_operation("doc_a", 30)
        scheduler.tracking_manager.record_operation("doc_b", 50)
        status = await scheduler.get_scheduler_status()
        assert status["is_running"] is True
        assert status["documents_tracked"] == 2
        assert status["documents_needing_snapshot"] == 1
        assert "doc_b" in status["documents_needing_snapshot_list"]
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_polling_detects_documents(self, scheduler):
        scheduler.tracking_manager.record_operation("doc_1", 30)
        scheduler.tracking_manager.record_operation("doc_2", 50)
        scheduler.tracking_manager.record_operation("doc_3", 40)
        docs = scheduler.tracking_manager.get_documents_needing_snapshot()
        assert "doc_2" in docs

    @pytest.mark.asyncio
    async def test_scheduler_multiple_documents(self, scheduler):
        for i in range(3):
            scheduler.tracking_manager.record_operation(f"doc_{i}", 50)
        docs = scheduler.tracking_manager.get_documents_needing_snapshot()
        assert len(docs) >= 3


class TestSnapshotSchedulerIntegration:
    @pytest.fixture
    def mock_versioning_service(self):
        service = AsyncMock()
        service.create_version = AsyncMock(return_value=("version-id", 1))
        return service

    @pytest.fixture
    async def scheduler(self, mock_versioning_service):
        SnapshotScheduler(mock_versioning_service, poll_interval=1).tracking_manager._trackers.clear()
        scheduler = SnapshotScheduler(mock_versioning_service, poll_interval=1)
        scheduler.tracking_manager._trackers.clear()
        scheduler.yjs_parser.get_document_text = lambda doc_id: f"content for {doc_id}"
        yield scheduler
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_complete_snapshot_workflow(self, scheduler):
        doc_id = "complete_test"
        for _ in range(5):
            should_snapshot, _ = scheduler.tracking_manager.record_operation(doc_id, 10)
            if should_snapshot:
                break
        await scheduler._create_snapshot(doc_id)
        assert scheduler.versioning_service.create_version.called
        assert scheduler.tracking_manager.get_tracker_status(doc_id)["operations_since_snapshot"] == 0

    @pytest.mark.asyncio
    async def test_scheduler_task_runs_continuously(self, scheduler):
        await scheduler.start()
        await asyncio.sleep(0.1)
        assert scheduler.is_running
        assert not scheduler.task.done()
        await scheduler.stop()


class TestMonitoringEndpoints:
    def test_tracking_status_endpoint_format(self):
        tracker = OperationTrackingManager()
        tracker.record_operation("doc_test", 25)
        status = tracker.get_tracker_status("doc_test")
        assert "doc_id" in status
        assert "operations_since_snapshot" in status
        assert "should_snapshot" in status

    def test_statistics_calculation(self):
        tracker = OperationTrackingManager()
        tracker.record_operation("doc_1", 20)
        tracker.record_operation("doc_2", 50)
        tracker.record_operation("doc_3", 80)
        all_status = tracker.get_all_tracker_statuses()
        assert len(all_status) == 3
        assert all_status["doc_2"]["operations_since_snapshot"] == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
