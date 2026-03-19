"""
Yjs WebSocket server implementing the y-websocket protocol.

Handles sync step 1/2 handshake, incremental updates, and awareness.
Maintains a server-side Y.Doc for each room so autosave can read content.
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from utils import get_yjs_parser, get_tracking_manager
from utils.yjs_parser import (
    extract_yjs_update,
    MSG_SYNC, MSG_AWARENESS,
    SYNC_STEP1, SYNC_STEP2, SYNC_UPDATE,
)

logger = logging.getLogger("collabscribe.routes.websocket")

router = APIRouter()

# Each room holds a set of connected WebSocket clients.
yjs_rooms: dict[str, set[WebSocket]] = {}

# Get utility instances
yjs_parser = get_yjs_parser()
tracking_manager = get_tracking_manager()

# Debounce state for snapshots
_snapshot_deadline: dict[str, float] = {}   # room -> loop-time when to fire
_snapshot_tasks: dict[str, asyncio.Task] = {}  # room -> running task (one per room)
_last_saved_hash: dict[str, int] = {}  # room -> hash of last saved content


@router.websocket("/yjs/{room}")
async def yjs_websocket(ws: WebSocket, room: str) -> None:
    """
    WebSocket endpoint implementing the y-websocket server protocol.

    Protocol handling:
      - Sync step 1: Client sends state vector. Server responds with
        sync step 2 (diff) + sync step 1 (our SV) to get client state.
      - Sync step 2: Client sends its state as an update. Applied to
        server Y.Doc. NOT broadcast (this is initial sync only).
      - Sync update: Incremental edit. Applied to Y.Doc, broadcast to
        all other peers, counted for autosave threshold.
      - Awareness: Broadcast to all other peers, not applied to Y.Doc.
    """
    await ws.accept()
    yjs_rooms.setdefault(room, set()).add(ws)
    logger.info(f"WebSocket connected to room {room} ({len(yjs_rooms[room])} peers)")

    try:
        while True:
            data = await ws.receive_bytes()

            if len(data) < 2:
                continue

            msg_type = data[0]

            if msg_type == MSG_SYNC:
                sync_type = data[1]

                if sync_type == SYNC_STEP1:
                    # Client is requesting sync — respond with our state
                    try:
                        responses = yjs_parser.handle_sync_step1(room, data)
                        for resp in responses:
                            await ws.send_bytes(resp)
                        logger.info(f"Room {room}: sync handshake (step 1 → {len(responses)} responses)")
                    except Exception as e:
                        logger.warning(f"Room {room}: sync step 1 failed: {e}", exc_info=True)

                elif sync_type == SYNC_STEP2:
                    # Client sending its state in response to our step 1
                    try:
                        yjs_parser.handle_sync_step2(room, data)
                        content = yjs_parser.get_document_text(room)
                        logger.info(f"Room {room}: sync step 2 received, doc={len(content)} chars")
                    except Exception as e:
                        logger.warning(f"Room {room}: sync step 2 failed: {e}", exc_info=True)
                    # Do NOT broadcast step 2 — it's part of initial sync

                elif sync_type == SYNC_UPDATE:
                    # Incremental edit — apply, broadcast, schedule autosave
                    try:
                        yjs_parser.handle_sync_update(room, data)
                    except Exception as e:
                        logger.warning(f"Room {room}: sync update apply failed: {e}", exc_info=True)

                    # Track ops for monitoring & schedule inactivity autosave
                    try:
                        update_payload = extract_yjs_update(data)
                        if update_payload and len(update_payload) > 0:
                            tracking_manager.record_operation(room, 1)
                            _trigger_snapshot(room)
                    except Exception as e:
                        logger.warning(f"Room {room}: op tracking failed: {e}")

                    # Broadcast sync updates to all other peers
                    await _broadcast(room, ws, data)

            elif msg_type == MSG_AWARENESS:
                # Awareness updates — broadcast to ALL peers including sender
                # (keeps the y-websocket provider's messageReconnectTimeout alive)
                await _broadcast(room, None, data)

    except WebSocketDisconnect:
        logger.debug(f"WebSocket disconnected from room {room}")
    except Exception as exc:
        logger.error(f"WebSocket error in room {room}: {exc}")
    finally:
        yjs_rooms.get(room, set()).discard(ws)
        if room in yjs_rooms and not yjs_rooms[room]:
            del yjs_rooms[room]
            logger.debug(f"Room {room} is now empty, deleted")


async def _broadcast(room: str, sender: WebSocket, data: bytes) -> None:
    """Broadcast binary data to all peers in a room except the sender."""
    peers = yjs_rooms.get(room, set())
    closed: list[WebSocket] = []
    for peer in peers:
        if peer is sender:
            continue
        try:
            await peer.send_bytes(data)
        except Exception:
            closed.append(peer)
    for c in closed:
        peers.discard(c)


def _trigger_snapshot(room: str) -> None:
    """
    Schedule a snapshot 2 seconds from now (debounced).

    Each call pushes the deadline forward. Only one task per room
    is ever running — it loops until the deadline is reached.
    """
    loop = asyncio.get_event_loop()
    _snapshot_deadline[room] = loop.time() + 2  # push deadline

    # Start a task only if one isn't already running for this room
    if room not in _snapshot_tasks or _snapshot_tasks[room].done():
        _snapshot_tasks[room] = asyncio.create_task(_do_snapshot(room))


async def _do_snapshot(room: str) -> None:
    """
    Wait until the debounce deadline passes, then create one snapshot.
    """
    try:
        loop = asyncio.get_event_loop()
        # Wait until no new deadline has been pushed for 2s
        while True:
            deadline = _snapshot_deadline.get(room, loop.time())
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            await asyncio.sleep(remaining)

        content = yjs_parser.get_document_text(room)
        if not content or not content.strip():
            logger.debug(f"Auto-snapshot skipped for {room}: no content")
            return

        # Skip if content hasn't changed since last save
        content_hash = hash(content)
        if _last_saved_hash.get(room) == content_hash:
            logger.debug(f"Auto-snapshot skipped for {room}: content unchanged")
            return

        from database import get_pool
        from services import VersioningService

        pool = get_pool()
        service = VersioningService(pool)
        version_id, version_num = await service.create_version(room, content)

        _last_saved_hash[room] = content_hash
        logger.info(f"Auto-snapshot for {room}: version {version_num} ({version_id})")
        tracking_manager.mark_snapshot_created(room)

        # Notify connected clients about the autosave via Socket.IO
        try:
            from socket_handlers.handlers import sio
            await sio.emit("autosave", {
                "version_number": version_num,
                "doc_id": room,
            }, room=room)
        except Exception:
            pass  # non-critical
    except Exception as e:
        logger.error(f"Auto-snapshot failed for {room}: {e}")
    finally:
        _snapshot_deadline.pop(room, None)
        _snapshot_tasks.pop(room, None)
