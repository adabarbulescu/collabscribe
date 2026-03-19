"""
Unit tests for Yjs integration utilities.
"""

import time

import pytest

from utils import (
    DocumentOperationTracker,
    OperationTrackingManager,
    YjsParser,
    count_operations,
    extract_text_from_update,
    get_tracking_manager,
    get_yjs_parser,
)


class TestYjsParser:
    def test_yjs_parser_initialization(self):
        parser = YjsParser()
        assert isinstance(parser, YjsParser)
        assert hasattr(parser, "_docs")

    def test_get_yjs_parser_singleton(self):
        parser1 = get_yjs_parser()
        parser2 = get_yjs_parser()
        assert parser1 is parser2

    def test_extract_text_empty_update(self):
        assert extract_text_from_update(b"") == ""

    def test_count_operations_empty(self):
        assert count_operations(b"") == 0

    def test_count_operations_small_update(self):
        assert count_operations(b"x" * 5) >= 1

    def test_count_operations_large_update(self):
        assert count_operations(b"x" * 100) > count_operations(b"x" * 10)

    def test_reset_document(self):
        parser = YjsParser()
        parser.reset_document()
        assert isinstance(parser.get_current_text(), str)

    def test_analyze_update(self):
        analysis = YjsParser.analyze_update(b"test_update")
        assert analysis["size"] == 11
        assert "estimated_ops" in analysis
        assert "type" in analysis
        assert "has_content" in analysis


class TestOperationTracking:
    def test_tracker_initialization(self):
        tracker = DocumentOperationTracker("test_doc")
        assert tracker.doc_id == "test_doc"
        assert tracker.operation_count == 0
        assert tracker.last_operation_time is None

    def test_record_single_operation(self):
        tracker = DocumentOperationTracker("test_doc")
        should_snapshot, _ = tracker.record_operation()
        assert not should_snapshot
        assert tracker.operation_count == 1
        assert tracker.last_operation_time is not None

    def test_operation_threshold_reached(self):
        tracker = DocumentOperationTracker("test_doc")
        for _ in range(50):
            should_snapshot, reason = tracker.record_operation()
        assert should_snapshot
        assert "threshold crossed" in reason.lower()

    def test_multiple_operations_at_once(self):
        tracker = DocumentOperationTracker("test_doc")
        should_snapshot, _ = tracker.record_operation(op_count=25)
        assert not should_snapshot
        should_snapshot, reason = tracker.record_operation(op_count=26)
        assert should_snapshot
        assert "threshold crossed" in reason.lower()

    def test_mark_snapshot_created_resets(self):
        tracker = DocumentOperationTracker("test_doc")
        tracker.record_operation(op_count=30)
        tracker.mark_snapshot_created()
        assert tracker.operation_count == 0
        assert tracker.last_snapshot_time is not None

    def test_time_threshold_check(self):
        tracker = DocumentOperationTracker("test_doc")
        tracker.record_operation(op_count=10)
        tracker.mark_snapshot_created()
        tracker.record_operation(op_count=1)
        tracker.last_snapshot_time = time.time() - 305

        manager = OperationTrackingManager()
        manager._trackers["test_doc"] = tracker
        assert "test_doc" in manager.get_documents_needing_snapshot()

    def test_tracker_status(self):
        tracker = DocumentOperationTracker("test_doc")
        tracker.record_operation(op_count=15)
        status = tracker.get_status()
        assert status["doc_id"] == "test_doc"
        assert status["operations_since_snapshot"] == 15
        assert status["operation_threshold"] == 50
        assert status["time_threshold_seconds"] == 300
        assert status["should_snapshot"] is False

    def test_get_tracking_manager_singleton(self):
        assert get_tracking_manager() is get_tracking_manager()

    def test_manager_get_or_create_tracker(self):
        manager = OperationTrackingManager()
        assert manager.get_or_create_tracker("doc_a") is manager.get_or_create_tracker("doc_a")

    def test_manager_record_operation(self):
        manager = OperationTrackingManager()
        should_snapshot, _ = manager.record_operation("doc_b", op_count=10)
        assert not should_snapshot
        assert manager.get_tracker_status("doc_b")["operations_since_snapshot"] == 10

    def test_manager_documents_needing_snapshot(self):
        manager = OperationTrackingManager()
        manager.record_operation("doc_a", op_count=25)
        manager.record_operation("doc_b", op_count=50)
        needing_snapshot = manager.get_documents_needing_snapshot()
        assert "doc_b" in needing_snapshot
        assert "doc_a" not in needing_snapshot

    def test_manager_mark_snapshot_created(self):
        manager = OperationTrackingManager()
        manager.record_operation("doc_c", op_count=30)
        manager.mark_snapshot_created("doc_c")
        status = manager.get_tracker_status("doc_c")
        assert status["operations_since_snapshot"] == 0
        assert status["last_snapshot_time"] is not None

    def test_manager_clear_tracker(self):
        manager = OperationTrackingManager()
        manager.record_operation("doc_d", op_count=5)
        manager.clear_tracker("doc_d")
        assert manager.get_tracker_status("doc_d") is None

    def test_manager_all_tracker_statuses(self):
        manager = OperationTrackingManager()
        manager.record_operation("doc_e", op_count=10)
        manager.record_operation("doc_f", op_count=20)
        manager.record_operation("doc_g", op_count=30)
        all_statuses = manager.get_all_tracker_statuses()
        assert len(all_statuses) == 3
        assert all_statuses["doc_f"]["operations_since_snapshot"] == 20


class TestYjsAndTrackingIntegration:
    def test_parse_and_track_workflow(self):
        parser = get_yjs_parser()
        manager = get_tracking_manager()
        test_update = b"x" * 50
        assert isinstance(extract_text_from_update(test_update), str)
        op_count = count_operations(test_update)
        assert op_count > 0
        manager.record_operation("doc_integrated", op_count)
        assert manager.get_tracker_status("doc_integrated")["operations_since_snapshot"] == op_count

    def test_multiple_updates_accumulate(self):
        manager = get_tracking_manager()
        doc_id = "doc_accumulate"
        manager.record_operation(doc_id, 10)
        manager.record_operation(doc_id, 15)
        manager.record_operation(doc_id, 20)
        assert manager.get_tracker_status(doc_id)["operations_since_snapshot"] == 45

    def test_snapshot_and_reset_workflow(self):
        manager = get_tracking_manager()
        doc_id = "doc_snapshot_workflow"
        manager.record_operation(doc_id, 40)
        manager.mark_snapshot_created(doc_id)
        manager.record_operation(doc_id, 30)
        assert manager.get_tracker_status(doc_id)["operations_since_snapshot"] == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
