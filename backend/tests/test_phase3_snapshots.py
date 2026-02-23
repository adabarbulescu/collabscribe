"""
Unit tests for background snapshot scheduler.

Tests:
- SnapshotScheduler initialization and lifecycle
- Polling mechanism and document detection
- Snapshot creation workflow
- Error handling and recovery
- Monitoring endpoints functionality
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from tasks import SnapshotScheduler
from utils import OperationTrackingManager


class TestSnapshotScheduler:
    """Test SnapshotScheduler functionality."""

    @pytest.fixture
    def mock_versioning_service(self):
        """Create mock VersioningService."""
        service = AsyncMock()
        service.create_version = AsyncMock(return_value=("version-id-123", 1))
        return service

    @pytest.fixture
    def scheduler(self, mock_versioning_service):
        """Create SnapshotScheduler with mock service."""
        return SnapshotScheduler(
            mock_versioning_service,
            poll_interval=1  # 1 second for faster tests
        )

    def test_scheduler_initialization(self, scheduler):
        """Test scheduler initializes correctly."""
        assert not scheduler.is_running
        assert scheduler.poll_interval == 1
        assert scheduler.task is None

    @pytest.mark.asyncio
    async def test_scheduler_start(self, scheduler):
        """Test scheduler starts successfully."""
        await scheduler.start()
        assert scheduler.is_running
        assert scheduler.task is not None
        
        # Cleanup
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_start_idempotent(self, scheduler):
        """Test that starting twice doesn't create multiple tasks."""
        await scheduler.start()
        task1 = scheduler.task
        
        # Try to start again
        await scheduler.start()
        task2 = scheduler.task
        
        # Should be same task
        assert task1 == task2
        
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_stop(self, scheduler):
        """Test scheduler stops gracefully."""
        await scheduler.start()
        assert scheduler.is_running
        
        await scheduler.stop()
        assert not scheduler.is_running

    @pytest.mark.asyncio
    async def test_scheduler_stop_idempotent(self, scheduler):
        """Test that stopping twice is safe."""
        await scheduler.start()
        await scheduler.stop()
        # Should not raise error
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_creates_snapshot_for_document(self, scheduler):
        """Test that scheduler creates snapshot for document exceeding threshold."""
        doc_id = "test_doc"
        
        # Record operations to exceed threshold
        tracker = scheduler.tracking_manager.get_or_create_tracker(doc_id)
        tracker.operation_count = 50  # Exceeds threshold
        
        # Create snapshot
        await scheduler._create_snapshot(doc_id)
        
        # Verify version was created
        scheduler.versioning_service.create_version.assert_called_once()
        
        # Verify counters were reset
        status = scheduler.tracking_manager.get_tracker_status(doc_id)
        assert status["operations_since_snapshot"] == 0

    @pytest.mark.asyncio
    async def test_scheduler_handles_missing_document(self, scheduler):
        """Test scheduler handles non-existent document gracefully."""
        from services import DocumentNotFoundError
        
        # Mock service to raise DocumentNotFoundError
        scheduler.versioning_service.create_version = AsyncMock(
            side_effect=DocumentNotFoundError("Not found")
        )
        
        # Should not raise, just log
        await scheduler._create_snapshot("nonexistent_doc")
        
        # Tracker should be cleared
        status = scheduler.tracking_manager.get_tracker_status("nonexistent_doc")
        assert status is None

    @pytest.mark.asyncio
    async def test_scheduler_status(self, scheduler):
        """Test getting scheduler status."""
        await scheduler.start()
        
        # Record some operations
        scheduler.tracking_manager.record_operation("doc_a", 30)
        scheduler.tracking_manager.record_operation("doc_b", 50)
        
        status = await scheduler.get_scheduler_status()
        
        assert status["is_running"] == True
        assert status["poll_interval"] == 1
        assert status["documents_tracked"] == 2
        assert status["documents_needing_snapshot"] == 1
        assert "doc_b" in status["documents_needing_snapshot_list"]
        
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_polling_detects_documents(self, scheduler):
        """Test that scheduler polling detects documents exceeding thresholds."""
        # Create documents with operations
        scheduler.tracking_manager.record_operation("doc_1", 30)
        scheduler.tracking_manager.record_operation("doc_2", 50)  # Exceeds
        scheduler.tracking_manager.record_operation("doc_3", 40)
        
        # Get documents needing snapshot
        docs = scheduler.tracking_manager.get_documents_needing_snapshot()
        
        # Should detect doc_2
        assert len(docs) >= 1
        assert "doc_2" in docs

    @pytest.mark.asyncio
    async def test_scheduler_multiple_documents(self, scheduler):
        """Test scheduler handles multiple documents in one cycle."""
        # Set up multiple documents exceeding threshold
        for i in range(3):
            scheduler.tracking_manager.record_operation(f"doc_{i}", 50)
        
        # Verify all detected
        docs = scheduler.tracking_manager.get_documents_needing_snapshot()
        assert len(docs) >= 3


class TestSnapshotSchedulerIntegration:
    """Integration tests for snapshot scheduler."""

    @pytest.fixture
    def mock_versioning_service(self):
        """Create mock VersioningService."""
        service = AsyncMock()
        service.create_version = AsyncMock(return_value=("version-id", 1))
        return service

    @pytest.fixture
    async def scheduler(self, mock_versioning_service):
        """Create and start scheduler."""
        scheduler = SnapshotScheduler(
            mock_versioning_service,
            poll_interval=1
        )
        yield scheduler
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_complete_snapshot_workflow(self, scheduler):
        """Test complete workflow: operations → threshold → snapshot."""
        doc_id = "complete_test"
        
        # Define document but don't start scheduler yet
        # Record operations  
        for i in range(5):
            should_snapshot, _ = scheduler.tracking_manager.record_operation(doc_id, 10)
            if should_snapshot:
                break
        
        # Now manually trigger snapshot (what scheduler would do)
        await scheduler._create_snapshot(doc_id)
        
        # Verify workflow completed
        assert scheduler.versioning_service.create_version.called
        status = scheduler.tracking_manager.get_tracker_status(doc_id)
        assert status["operations_since_snapshot"] == 0

    @pytest.mark.asyncio
    async def test_scheduler_task_runs_continuously(self, scheduler):
        """Test that scheduler task runs in background."""
        await scheduler.start()
        
        # Give it time to start
        await asyncio.sleep(0.1)
        
        # Scheduler should still be running
        assert scheduler.is_running
        assert not scheduler.task.done()
        
        await scheduler.stop()


class TestMonitoringEndpoints:
    """Test monitoring endpoints (would be integration tests with FastAPI)."""

    def test_scheduler_status_endpoint_format(self):
        """Test scheduler status endpoint returns expected format."""
        from routes.monitoring import get_scheduler_status
        
        # This would require async test client
        # Placeholder for full integration test
        pass

    def test_tracking_status_endpoint_format(self):
        """Test tracking status endpoint format."""
        tracker = OperationTrackingManager()
        tracker.record_operation("doc_test", 25)
        
        status = tracker.get_tracker_status("doc_test")
        
        # Verify structure
        assert "doc_id" in status
        assert "operations_since_snapshot" in status
        assert "should_snapshot" in status
        assert "last_operation_time" in status

    def test_statistics_calculation(self):
        """Test statistics aggregation."""
        tracker = OperationTrackingManager()
        
        # Create multiple documents
        tracker.record_operation("doc_1", 20)
        tracker.record_operation("doc_2", 50)
        tracker.record_operation("doc_3", 80)
        
        all_status = tracker.get_all_tracker_statuses()
        
        # Verify count
        assert len(all_status) == 3
        
        # Verify individual statuses
        assert all_status["doc_1"]["operations_since_snapshot"] == 20
        assert all_status["doc_2"]["operations_since_snapshot"] == 50
        assert all_status["doc_3"]["operations_since_snapshot"] == 80


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
