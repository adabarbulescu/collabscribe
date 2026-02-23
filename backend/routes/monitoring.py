"""
Monitoring endpoints for background tasks and snapshot scheduler.

Provides visibility into snapshot status, operation counts, and
document version tracking for analytics and debugging.
"""

import logging
from fastapi import APIRouter, HTTPException, Query

from tasks import get_snapshot_scheduler
from utils import get_tracking_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["monitoring"])


@router.get("/scheduler/status")
async def get_scheduler_status():
    """
    Get snapshot scheduler status and monitored documents.
    
    Returns comprehensive status including:
    - Scheduler running state
    - Poll interval configuration
    - Count of documents being tracked
    - Count of documents exceeding thresholds
    - Detailed status per document (operations, timing)
    
    **Response:**
    ```json
    {
        "is_running": true,
        "poll_interval": 60,
        "documents_tracked": 5,
        "documents_needing_snapshot": 2,
        "documents_needing_snapshot_list": ["doc_abc", "doc_def"],
        "tracked_documents": {
            "doc_abc": {
                "operations_since_snapshot": 52,
                "session_operations": 156,
                "operation_threshold": 50,
                "time_threshold_seconds": 300,
                "should_snapshot": true,
                "time_since_snapshot": 45.3,
                "time_since_last_operation": 2.1
            }
        },
        "timestamp": "2026-02-18T10:30:45.123456"
    }
    ```
    """
    try:
        scheduler = await get_snapshot_scheduler()
        status = await scheduler.get_scheduler_status()
        return status
    except Exception as e:
        logger.error(f"Failed to get scheduler status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scheduler status")


@router.get("/tracking/document/{doc_id}")
async def get_document_tracking_status(doc_id: str):
    """
    Get operation tracking status for a specific document.
    
    Shows operation count since last snapshot, timing info,
    and whether snapshot threshold is exceeded.
    
    **Path Parameters:**
    - `doc_id`: Document identifier
    
    **Response:**
    ```json
    {
        "doc_id": "abc123",
        "operations_since_snapshot": 35,
        "session_operations": 128,
        "operation_threshold": 50,
        "time_threshold_seconds": 300,
        "time_since_snapshot": 120.5,
        "time_since_last_operation": 3.2,
        "should_snapshot": false,
        "last_operation_time": "2026-02-18T10:29:45.123456",
        "last_snapshot_time": "2026-02-18T10:26:45.987654"
    }
    ```
    
    **Returns 404 if document not found (no tracking data)**
    """
    tracking_manager = get_tracking_manager()
    status = tracking_manager.get_tracker_status(doc_id)
    
    if not status:
        raise HTTPException(status_code=404, detail=f"Document not tracked: {doc_id}")
    
    return status


@router.get("/tracking/all")
async def get_all_tracking_status():
    """
    Get operation tracking status for all documents.
    
    Returns dictionary mapping each document ID to its tracking status.
    Useful for monitoring dashboard or analytics.
    
    **Response:**
    ```json
    {
        "doc_abc": {
            "operations_since_snapshot": 35,
            "session_operations": 128,
            ...
        },
        "doc_def": {
            "operations_since_snapshot": 52,
            "session_operations": 256,
            ...
        }
    }
    ```
    """
    tracking_manager = get_tracking_manager()
    return tracking_manager.get_all_tracker_statuses()


@router.post("/tracking/snapshot/{doc_id}")
async def trigger_snapshot_manual(doc_id: str):
    """
    Manually trigger a snapshot for a specific document.
    
    Useful for testing or forcing snapshots outside normal thresholds.
    
    **Path Parameters:**
    - `doc_id`: Document identifier
    
    **Response:**
    ```json
    {
        "doc_id": "abc123",
        "status": "snapshot_triggered",
        "message": "Manual snapshot triggered for doc_abc"
    }
    ```
    
    **Returns 404 if document not found**
    """
    try:
        tracking_manager = get_tracking_manager()
        status = tracking_manager.get_tracker_status(doc_id)
        
        if not status:
            raise HTTPException(status_code=404, detail=f"Document not tracked: {doc_id}")
        
        # Reset thresholds to trigger snapshot on next scheduler poll
        # This forces snapshot by resetting operation count
        scheduler = await get_snapshot_scheduler()
        await scheduler._create_snapshot(doc_id)
        
        return {
            "doc_id": doc_id,
            "status": "snapshot_triggered",
            "message": f"Manual snapshot triggered for {doc_id}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger manual snapshot for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger snapshot")


@router.get("/tracking/stats")
async def get_tracking_statistics():
    """
    Get aggregate statistics about document tracking.
    
    Provides high-level metrics about active documents,
    operation rates, and snapshot activity.
    
    **Response:**
    ```json
    {
        "total_documents_tracked": 8,
        "documents_needing_snapshot": 3,
        "total_operations_recorded": 1250,
        "average_operations_per_document": 156.25,
        "documents_exceeding_operation_threshold": 3,
        "documents_exceeding_time_threshold": 1,
        "most_active_document": {
            "doc_id": "doc_abc",
            "operations": 256
        },
        "least_active_document": {
            "doc_id": "doc_xyz",
            "operations": 5
        }
    }
    ```
    """
    tracking_manager = get_tracking_manager()
    all_statuses = tracking_manager.get_all_tracker_statuses()
    
    if not all_statuses:
        return {
            "total_documents_tracked": 0,
            "documents_needing_snapshot": 0,
            "total_operations_recorded": 0,
            "average_operations_per_document": 0,
            "documents_exceeding_operation_threshold": 0,
            "documents_exceeding_time_threshold": 0,
            "most_active_document": None,
            "least_active_document": None,
        }
    
    # Calculate statistics
    total_ops = sum(s["operations_since_snapshot"] for s in all_statuses.values())
    avg_ops = total_ops / len(all_statuses) if all_statuses else 0
    
    op_threshold_exceeded = sum(
        1 for s in all_statuses.values() 
        if s["operations_since_snapshot"] >= s["operation_threshold"]
    )
    
    time_threshold_exceeded = sum(
        1 for s in all_statuses.values()
        if s["time_since_snapshot"] and s["time_since_snapshot"] >= s["time_threshold_seconds"]
    )
    
    # Find most/least active
    sorted_by_ops = sorted(
        all_statuses.items(),
        key=lambda x: x[1]["operations_since_snapshot"],
        reverse=True,
    )
    
    return {
        "total_documents_tracked": len(all_statuses),
        "documents_needing_snapshot": len(tracking_manager.get_documents_needing_snapshot()),
        "total_operations_recorded": total_ops,
        "average_operations_per_document": round(avg_ops, 2),
        "documents_exceeding_operation_threshold": op_threshold_exceeded,
        "documents_exceeding_time_threshold": time_threshold_exceeded,
        "most_active_document": {
            "doc_id": sorted_by_ops[0][0],
            "operations": sorted_by_ops[0][1]["operations_since_snapshot"],
        } if sorted_by_ops else None,
        "least_active_document": {
            "doc_id": sorted_by_ops[-1][0],
            "operations": sorted_by_ops[-1][1]["operations_since_snapshot"],
        } if sorted_by_ops else None,
    }
