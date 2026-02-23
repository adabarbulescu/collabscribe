"""
Socket.IO event handlers for awareness, user count tracking, and Yjs CRDT sync.

Features:
- User awareness and cursor position tracking
- Connected user counts per document
- Yjs CRDT update relay with text extraction
- Operation counting for auto-snapshot thresholds
"""

from __future__ import annotations

import logging
from typing import Any

import socketio as socketio_lib

from utils import get_yjs_parser, count_operations, get_tracking_manager

logger = logging.getLogger("collab.socketio")

# Socket.IO server (async mode for uvicorn)
sio = socketio_lib.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

# Track connected users per room  {doc_id: set(sid)}
sio_rooms: dict[str, set[str]] = {}

# Get utility instances
yjs_parser = get_yjs_parser()
tracking_manager = get_tracking_manager()


@sio.event
async def connect(sid: str, environ: dict[str, Any]) -> None:
    """
    Handle new Socket.IO client connection.

    Args:
        sid: Socket.IO session ID.
        environ: ASGI environ dict.
    """
    logger.info(f"Client connected: {sid}")


@sio.event
async def disconnect(sid: str) -> None:
    """
    Handle Socket.IO client disconnection.

    Args:
        sid: Socket.IO session ID.
    """
    logger.info(f"Client disconnected: {sid}")
    for doc_id, members in list(sio_rooms.items()):
        if sid in members:
            members.discard(sid)
            await sio.emit(
                "user_count",
                {"count": len(members)},
                room=doc_id,
            )
            if not members:
                del sio_rooms[doc_id]


@sio.event
async def join_room(sid: str, data: dict[str, Any]) -> None:
    """
    Handle client joining a document room.

    Args:
        sid: Socket.IO session ID.
        data: Message data containing 'doc_id'.
    """
    doc_id = data.get("doc_id", "default")
    await sio.enter_room(sid, doc_id)
    sio_rooms.setdefault(doc_id, set()).add(sid)
    
    # Initialize operation tracking for this document
    tracking_manager.get_or_create_tracker(doc_id)
    
    await sio.emit(
        "user_count",
        {"count": len(sio_rooms.get(doc_id, set()))},
        room=doc_id,
    )
    logger.info(f"{sid} joined room {doc_id} ({len(sio_rooms[doc_id])} users)")


@sio.event
async def awareness_update(sid: str, data: dict[str, Any]) -> None:
    """
    Broadcast cursor/awareness info to all clients in same room.

    Args:
        sid: Socket.IO session ID.
        data: Awareness update data containing 'doc_id'.
    """
    doc_id = data.get("doc_id", "default")
    await sio.emit("awareness_update", data, room=doc_id, skip_sid=sid)


@sio.event
async def yjs_update(sid: str, data: dict[str, Any]) -> None:
    """
    Handle Yjs CRDT update from client.
    
    Receives binary Yjs updates, extracts text content,
    tracks operations for auto-snapshot thresholds,
    and relays to other clients.

    Args:
        sid: Socket.IO session ID.
        data: Message data containing:
            - 'doc_id': Document identifier (str)
            - 'update': Binary Yjs update (bytes)
            
    Called from frontend when document changes via Yjs.
    """
    try:
        doc_id = data.get("doc_id", "default")
        update_bytes = data.get("update")
        
        if not update_bytes:
            logger.warning(f"Received empty Yjs update from {sid} in {doc_id}")
            return
        
        # Convert update to bytes if needed
        if isinstance(update_bytes, str):
            update_bytes = update_bytes.encode('latin-1')
        elif not isinstance(update_bytes, bytes):
            update_bytes = bytes(update_bytes)
        
        logger.debug(f"Received Yjs update: {len(update_bytes)} bytes from {sid} in {doc_id}")
        
        # Extract text content from update
        extracted_text = yjs_parser.extract_text_from_update(update_bytes)
        
        # Estimate operation count from update size
        op_count = count_operations(update_bytes)
        
        # Record operation for snapshot threshold tracking
        should_snapshot, reason = tracking_manager.record_operation(doc_id, op_count)
        
        if should_snapshot:
            logger.info(f"Auto-snapshot triggered for {doc_id}: {reason}")
            # Snapshot will be created by tasks/snapshot_scheduler.py
        
        # Relay update to all other clients in room
        await sio.emit(
            "yjs_update",
            {
                "doc_id": doc_id,
                "update": update_bytes,  # Binary relay
                "from_sid": sid,
            },
            room=doc_id,
            skip_sid=sid,
        )
        
        logger.debug(
            f"Relayed Yjs update ({len(update_bytes)} bytes, ~{op_count} ops) "
            f"in {doc_id} from {sid}"
        )
        
    except Exception as e:
        logger.error(f"Error handling yjs_update from {sid}: {e}", exc_info=True)
        await sio.emit(
            "error",
            {"message": "Failed to process Yjs update"},
            room=sid,
        )


@sio.event
async def sync_state(sid: str, data: dict[str, Any]) -> None:
    """
    Handle full document sync request.
    
    Client requests full document state when joining.
    Currently a placeholder; client-side Yjs handles state reconstruction.

    Args:
        sid: Socket.IO session ID.
        data: Message data containing 'doc_id'.
    """
    doc_id = data.get("doc_id", "default")
    logger.info(f"Sync state requested for {doc_id} by {sid}")
    
    # Client-side Yjs handles state reconstruction


def get_combined_app(app):
    """
    Wrap FastAPI app with Socket.IO ASGI app.

    Args:
        app: FastAPI application instance.

    Returns:
        Socket.IO ASGI wrapped FastAPI app.
    """
    return socketio_lib.ASGIApp(sio, other_asgi_app=app)
