"""
Operation tracking for active documents.

Tracks real-time operation counts and timing for documents
to determine when snapshots should be created.

Used by WebSocket handlers to feed operation data to snapshot scheduler.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class DocumentOperationTracker:
    """Tracks operations for a single document."""
    
    doc_id: str
    operation_count: int = 0  # Total operations since last snapshot
    last_operation_time: Optional[float] = None
    last_snapshot_time: Optional[float] = None
    current_session_ops: int = 0  # Operations in current session
    
    # Thresholds for auto-snapshot
    OPERATION_THRESHOLD: int = 50  # Create snapshot after 50 ops
    TIME_THRESHOLD_SECONDS: int = 300  # Create snapshot after 5 minutes
    
    def record_operation(self, op_count: int = 1) -> tuple[bool, str]:
        """
        Record one or more operations for this document.
        
        Only returns True when a threshold is CROSSED (transition),
        not every time the count is above the threshold.
        
        Args:
            op_count: Number of operations to record (default 1)
            
        Returns:
            Tuple of (should_snapshot: bool, reason: str)
            - should_snapshot: True if a threshold was just crossed
            - reason: Description of which threshold triggered
        """
        current_time = time.time()
        old_count = self.operation_count
        self.operation_count += op_count
        self.current_session_ops += op_count
        self.last_operation_time = current_time
        
        # Check operation threshold: only fire when CROSSING the boundary
        if old_count < self.OPERATION_THRESHOLD <= self.operation_count:
            reason = f"Operation threshold crossed ({self.operation_count} >= {self.OPERATION_THRESHOLD})"
            logger.info(f"Document {self.doc_id}: {reason}")
            return True, reason
        
        return False, "No threshold crossed"
    
    def mark_snapshot_created(self) -> None:
        """
        Mark that snapshot was created for this document.
        
        Resets operation counter and updates last snapshot time.
        """
        current_time = time.time()
        self.last_snapshot_time = current_time
        self.operation_count = 0
        logger.debug(f"Document {self.doc_id}: Snapshot created, counters reset")
    
    def get_status(self) -> dict:
        """
        Get current tracking status for this document.
        
        Returns:
            Dictionary with operation counts, thresholds, and timing info
        """
        current_time = time.time()
        
        time_since_snapshot = None
        if self.last_snapshot_time:
            time_since_snapshot = current_time - self.last_snapshot_time
        
        time_since_operation = None
        if self.last_operation_time:
            time_since_operation = current_time - self.last_operation_time
        
        return {
            "doc_id": self.doc_id,
            "operations_since_snapshot": self.operation_count,
            "session_operations": self.current_session_ops,
            "operation_threshold": self.OPERATION_THRESHOLD,
            "time_threshold_seconds": self.TIME_THRESHOLD_SECONDS,
            "time_since_snapshot": time_since_snapshot,
            "time_since_last_operation": time_since_operation,
            "should_snapshot": self.operation_count >= self.OPERATION_THRESHOLD,
            "last_operation_time": datetime.fromtimestamp(self.last_operation_time).isoformat() if self.last_operation_time else None,
            "last_snapshot_time": datetime.fromtimestamp(self.last_snapshot_time).isoformat() if self.last_snapshot_time else None,
        }


class OperationTrackingManager:
    """
    Manages operation tracking for all active documents.
    
    Centralized registry of DocumentOperationTracker instances,
    used by WebSocket handlers and snapshot scheduler.
    """
    
    def __init__(self):
        """Initialize operation tracking manager."""
        self._trackers: Dict[str, DocumentOperationTracker] = {}
        logger.info("Initialized OperationTrackingManager")
    
    def get_or_create_tracker(self, doc_id: str) -> DocumentOperationTracker:
        """
        Get or create tracker for a document.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            DocumentOperationTracker for the document
        """
        if doc_id not in self._trackers:
            self._trackers[doc_id] = DocumentOperationTracker(doc_id)
            logger.debug(f"Created operation tracker for {doc_id}")
        
        return self._trackers[doc_id]
    
    def record_operation(self, doc_id: str, op_count: int = 1) -> tuple[bool, str]:
        """
        Record operations for a document.
        
        Args:
            doc_id: Document identifier
            op_count: Number of operations
            
        Returns:
            Tuple of (should_snapshot: bool, reason: str)
        """
        tracker = self.get_or_create_tracker(doc_id)
        return tracker.record_operation(op_count)
    
    def mark_snapshot_created(self, doc_id: str) -> None:
        """
        Mark snapshot as created for document.
        
        Args:
            doc_id: Document identifier
        """
        tracker = self.get_or_create_tracker(doc_id)
        tracker.mark_snapshot_created()
    
    def get_tracker_status(self, doc_id: str) -> Optional[dict]:
        """
        Get status for document tracker.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Status dictionary or None if no tracker exists
        """
        if doc_id not in self._trackers:
            return None
        
        return self._trackers[doc_id].get_status()
    
    def get_all_tracker_statuses(self) -> Dict[str, dict]:
        """
        Get status for all document trackers.
        
        Returns:
            Dictionary mapping doc_id to status dict
        """
        return {
            doc_id: tracker.get_status()
            for doc_id, tracker in self._trackers.items()
        }
    
    def get_documents_needing_snapshot(self) -> list[str]:
        """
        Get list of documents that exceed snapshot thresholds.
        
        Used by snapshot scheduler to determine which documents
        need snapshots created.
        
        Returns:
            List of doc_ids that should be snapshotted
        """
        needing_snapshot = []
        
        for doc_id, tracker in self._trackers.items():
            if tracker.operation_count >= tracker.OPERATION_THRESHOLD:
                needing_snapshot.append(doc_id)
            elif tracker.last_snapshot_time:
                elapsed = time.time() - tracker.last_snapshot_time
                if elapsed >= tracker.TIME_THRESHOLD_SECONDS and tracker.operation_count > 0:
                    needing_snapshot.append(doc_id)
        
        return needing_snapshot
    
    def clear_tracker(self, doc_id: str) -> None:
        """
        Remove tracker for a document (e.g., when document closed).
        
        Args:
            doc_id: Document identifier
        """
        if doc_id in self._trackers:
            del self._trackers[doc_id]
            logger.debug(f"Cleared operation tracker for {doc_id}")


# Global instance
_tracking_manager: Optional[OperationTrackingManager] = None


def get_tracking_manager() -> OperationTrackingManager:
    """
    Get or create global operation tracking manager.
    
    Returns:
        Shared OperationTrackingManager instance
    """
    global _tracking_manager
    if _tracking_manager is None:
        _tracking_manager = OperationTrackingManager()
    
    return _tracking_manager
