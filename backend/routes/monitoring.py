"""Monitoring endpoints for snapshot status and operation tracking."""

import logging
from fastapi import APIRouter, HTTPException

from tasks import get_snapshot_scheduler
from utils import get_tracking_manager

logger = logging.getLogger("collabscribe.routes.monitoring")

router = APIRouter(prefix="/api/admin", tags=["monitoring"])


@router.get("/scheduler/status")
async def get_scheduler_status():
    """Return scheduler status and the current tracked-document summary."""
    try:
        scheduler = await get_snapshot_scheduler()
        status = await scheduler.get_scheduler_status()
        return status
    except Exception as exc:
        logger.error("Failed to get scheduler status: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to get scheduler status")


@router.get("/tracking/document/{doc_id}")
async def get_document_tracking_status(doc_id: str):
    """Return operation-tracking status for one document."""
    tracking_manager = get_tracking_manager()
    status = tracking_manager.get_tracker_status(doc_id)
    
    if not status:
        raise HTTPException(status_code=404, detail=f"Document not tracked: {doc_id}")
    
    return status


@router.get("/tracking/all")
async def get_all_tracking_status():
    """Return operation-tracking status for all tracked documents."""
    tracking_manager = get_tracking_manager()
    return tracking_manager.get_all_tracker_statuses()


@router.post("/tracking/snapshot/{doc_id}")
async def trigger_snapshot_manual(doc_id: str):
    """Create a snapshot immediately for a tracked document."""
    try:
        tracking_manager = get_tracking_manager()
        status = tracking_manager.get_tracker_status(doc_id)
        
        if not status:
            raise HTTPException(status_code=404, detail=f"Document not tracked: {doc_id}")
        
        scheduler = await get_snapshot_scheduler()
        await scheduler._create_snapshot(doc_id)
        
        return {
            "doc_id": doc_id,
            "status": "snapshot_triggered",
            "message": f"Manual snapshot triggered for {doc_id}",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to trigger manual snapshot for %s: %s", doc_id, exc)
        raise HTTPException(status_code=500, detail="Failed to trigger snapshot")


@router.get("/tracking/stats")
async def get_tracking_statistics():
    """Return aggregate statistics for all tracked documents."""
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
