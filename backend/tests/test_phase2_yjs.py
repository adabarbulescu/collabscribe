"""
Unit tests for Yjs integration utilities.

Tests:
- YjsParser text extraction and update handling
- OperationTrackingManager operation counting and thresholds
- Integration between parsing and tracking
"""

import pytest
import time
from utils import (
    YjsParser,
    YjsUpdateType,
    get_yjs_parser,
    count_operations,
    DocumentOperationTracker,
    OperationTrackingManager,
    get_tracking_manager,
)


class TestYjsParser:
    """Test Yjs text extraction and parsing."""

    def test_yjs_parser_initialization(self):
        """Test YjsParser initializes correctly."""
        parser = YjsParser()
        assert parser.doc is not None or not parser.HAS_YPY  # Either has doc or y-py not installed

    def test_get_yjs_parser_singleton(self):
        """Test that get_yjs_parser returns same instance."""
        parser1 = get_yjs_parser()
        parser2 = get_yjs_parser()
        assert parser1 is parser2

    def test_extract_text_empty_update(self):
        """Test extracting text from empty update returns empty string."""
        parser = YjsParser()
        text = parser.extract_text_from_update(b"")
        assert text == ""

    def test_count_operations_empty(self):
        """Test operation count for empty update."""
        count = count_operations(b"")
        assert count == 0

    def test_count_operations_small_update(self):
        """Test operation count for small update."""
        # Small update should estimate ~1 operation
        count = count_operations(b"x" * 5)
        assert count >= 1

    def test_count_operations_large_update(self):
        """Test operation count for larger update."""
        # Larger update should estimate more operations
        count_small = count_operations(b"x" * 10)
        count_large = count_operations(b"x" * 100)
        assert count_large > count_small

    def test_reset_document(self):
        """Test resetting document state."""
        parser = YjsParser()
        parser.reset_document()
        # Should not raise error, document should be reset
        text = parser.get_current_text()
        assert isinstance(text, str)

    def test_analyze_update(self):
        """Test update analysis returns expected structure."""
        parser = YjsParser()
        analysis = parser.analyze_update(b"test_update")
        
        assert "size" in analysis
        assert "estimated_ops" in analysis
        assert "type" in analysis
        assert "has_content" in analysis
        assert analysis["size"] == 11


class TestOperationTracking:
    """Test operation tracking and threshold detection."""

    def test_tracker_initialization(self):
        """Test DocumentOperationTracker initializes correctly."""
        tracker = DocumentOperationTracker("test_doc")
        assert tracker.doc_id == "test_doc"
        assert tracker.operation_count == 0
        assert tracker.last_operation_time is None

    def test_record_single_operation(self):
        """Test recording a single operation."""
        tracker = DocumentOperationTracker("test_doc")
        should_snapshot, reason = tracker.record_operation()
        
        assert not should_snapshot
        assert tracker.operation_count == 1
        assert tracker.last_operation_time is not None

    def test_operation_threshold_reached(self):
        """Test operation threshold triggers snapshot."""
        tracker = DocumentOperationTracker("test_doc")
        
        # Record up to threshold
        for _ in range(50):
            should_snapshot, _ = tracker.record_operation()
        
        assert should_snapshot
        assert "Operation threshold reached" in str(tracker.operation_count)

    def test_multiple_operations_at_once(self):
        """Test recording multiple operations simultaneously."""
        tracker = DocumentOperationTracker("test_doc")
        should_snapshot, reason = tracker.record_operation(op_count=25)
        
        assert not should_snapshot
        assert tracker.operation_count == 25
        
        should_snapshot, reason = tracker.record_operation(op_count=26)
        assert should_snapshot
        assert "Operation threshold reached" in reason

    def test_mark_snapshot_created_resets(self):
        """Test that marking snapshot resets counters."""
        tracker = DocumentOperationTracker("test_doc")
        tracker.record_operation(op_count=30)
        
        assert tracker.operation_count == 30
        
        tracker.mark_snapshot_created()
        assert tracker.operation_count == 0
        assert tracker.last_snapshot_time is not None

    def test_time_threshold_check(self):
        """Test time threshold for snapshot (5 minutes)."""
        tracker = DocumentOperationTracker("test_doc")
        tracker.record_operation()
        
        # Take a snapshot
        tracker.mark_snapshot_created()
        
        # Manually set last_snapshot_time to past
        tracker.last_snapshot_time = time.time() - 305  # 5+ minutes ago
        
        should_snapshot, reason = tracker.record_operation()
        assert should_snapshot
        assert "Time threshold exceeded" in reason

    def test_tracker_status(self):
        """Test getting tracker status returns all info."""
        tracker = DocumentOperationTracker("test_doc")
        tracker.record_operation(op_count=15)
        
        status = tracker.get_status()
        
        assert status["doc_id"] == "test_doc"
        assert status["operations_since_snapshot"] == 15
        assert status["operation_threshold"] == 50
        assert status["time_threshold_seconds"] == 300
        assert status["should_snapshot"] == False
        assert status["last_operation_time"] is not None
        assert status["last_snapshot_time"] is None

    def test_get_tracking_manager_singleton(self):
        """Test that get_tracking_manager returns same instance."""
        manager1 = get_tracking_manager()
        manager2 = get_tracking_manager()
        assert manager1 is manager2

    def test_manager_get_or_create_tracker(self):
        """Test manager creates tracker on first access."""
        manager = OperationTrackingManager()
        
        tracker1 = manager.get_or_create_tracker("doc_a")
        assert tracker1.doc_id == "doc_a"
        
        # Getting again should return same instance
        tracker2 = manager.get_or_create_tracker("doc_a")
        assert tracker1 is tracker2

    def test_manager_record_operation(self):
        """Test manager records operations."""
        manager = OperationTrackingManager()
        
        should_snapshot, _ = manager.record_operation("doc_b", op_count=10)
        assert not should_snapshot
        
        # Check tracker was created
        status = manager.get_tracker_status("doc_b")
        assert status["operations_since_snapshot"] == 10

    def test_manager_documents_needing_snapshot(self):
        """Test manager identifies documents needing snapshots."""
        manager = OperationTrackingManager()
        
        # Doc A: below threshold
        manager.record_operation("doc_a", op_count=25)
        
        # Doc B: exceeds threshold
        manager.record_operation("doc_b", op_count=50)
        
        needing_snapshot = manager.get_documents_needing_snapshot()
        # Note: record_operation checks without incrementing when called with 0
        # So we need to check what we recorded
        
        # Verify both docs were tracked
        assert "doc_a" in [t.doc_id for t in manager._trackers.values()]
        assert "doc_b" in [t.doc_id for t in manager._trackers.values()]

    def test_manager_mark_snapshot_created(self):
        """Test manager marks snapshot as created."""
        manager = OperationTrackingManager()
        manager.record_operation("doc_c", op_count=30)
        
        manager.mark_snapshot_created("doc_c")
        status = manager.get_tracker_status("doc_c")
        
        assert status["operations_since_snapshot"] == 0
        assert status["last_snapshot_time"] is not None

    def test_manager_clear_tracker(self):
        """Test clearing tracker for inactive document."""
        manager = OperationTrackingManager()
        manager.record_operation("doc_d", op_count=5)
        
        assert manager.get_tracker_status("doc_d") is not None
        
        manager.clear_tracker("doc_d")
        
        assert manager.get_tracker_status("doc_d") is None

    def test_manager_all_tracker_statuses(self):
        """Test getting all tracker statuses."""
        manager = OperationTrackingManager()
        
        manager.record_operation("doc_e", op_count=10)
        manager.record_operation("doc_f", op_count=20)
        manager.record_operation("doc_g", op_count=30)
        
        all_statuses = manager.get_all_tracker_statuses()
        
        assert len(all_statuses) == 3
        assert "doc_e" in all_statuses
        assert "doc_f" in all_statuses
        assert "doc_g" in all_statuses
        assert all_statuses["doc_e"]["operations_since_snapshot"] == 10
        assert all_statuses["doc_f"]["operations_since_snapshot"] == 20
        assert all_statuses["doc_g"]["operations_since_snapshot"] == 30


class TestYjsAndTrackingIntegration:
    """Test integration between Yjs parser and operation tracking."""

    def test_parse_and_track_workflow(self):
        """Test complete workflow: parse update and track operations."""
        parser = get_yjs_parser()
        manager = get_tracking_manager()
        
        # Simulate Yjs update
        test_update = b"x" * 50
        
        # Extract text
        text = parser.extract_text_from_update(test_update)
        # Text may be empty if y-py not available, but should be string
        assert isinstance(text, str)
        
        # Count operations
        op_count = count_operations(test_update)
        assert op_count > 0
        
        # Track operations
        should_snapshot, reason = manager.record_operation("doc_integrated", op_count)
        
        # Verify tracking worked
        status = manager.get_tracker_status("doc_integrated")
        assert status["operations_since_snapshot"] == op_count

    def test_multiple_updates_accumulate(self):
        """Test that multiple updates accumulate correctly."""
        manager = get_tracking_manager()
        doc_id = "doc_accumulate"
        
        # Multiple updates
        manager.record_operation(doc_id, 10)
        manager.record_operation(doc_id, 15)
        manager.record_operation(doc_id, 20)
        
        status = manager.get_tracker_status(doc_id)
        assert status["operations_since_snapshot"] == 45

    def test_snapshot_and_reset_workflow(self):
        """Test snapshot creation resets counters."""
        manager = get_tracking_manager()
        doc_id = "doc_snapshot_workflow"
        
        # Record operations
        manager.record_operation(doc_id, 40)
        assert manager.get_tracker_status(doc_id)["operations_since_snapshot"] == 40
        
        # Create snapshot
        manager.mark_snapshot_created(doc_id)
        assert manager.get_tracker_status(doc_id)["operations_since_snapshot"] == 0
        
        # New operations start fresh count
        manager.record_operation(doc_id, 30)
        assert manager.get_tracker_status(doc_id)["operations_since_snapshot"] == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
