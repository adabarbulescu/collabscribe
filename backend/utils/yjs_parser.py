"""
Yjs CRDT update parsing and text extraction.

Handles extraction of plain text content from Yjs binary updates
using the y-py Python bindings library.

Parses y-websocket protocol framing to extract actual Yjs updates
from the binary WebSocket messages.

Protocol format (y-websocket):
  byte[0] = message type: 0=sync, 1=awareness
  For sync (type 0):
    byte[1] = sync sub-type: 0=step1(request), 1=step2(state), 2=update
    For step2/update: byte[2:] = varuint-prefixed Yjs update bytes
"""

import logging
from typing import Optional
from enum import Enum

try:
    import y_py as ypy
    HAS_YPY = True
except ImportError:
    HAS_YPY = False

logger = logging.getLogger(__name__)

# y-websocket protocol constants
MSG_SYNC = 0
MSG_AWARENESS = 1
SYNC_STEP1 = 0
SYNC_STEP2 = 1
SYNC_UPDATE = 2


def _read_varuint(data: bytes, offset: int) -> tuple[int, int]:
    """Read a variable-length unsigned integer (lib0 encoding)."""
    result = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if byte < 0x80:
            break
        shift += 7
    return result, offset


def _write_varuint(value: int) -> bytes:
    """Encode a variable-length unsigned integer (lib0 encoding)."""
    buf = bytearray()
    while value > 0x7F:
        buf.append((value & 0x7F) | 0x80)
        value >>= 7
    buf.append(value & 0x7F)
    return bytes(buf)


def encode_sync_step2(update: bytes) -> bytes:
    """Encode a y-websocket sync step 2 message containing a Yjs update."""
    return bytes([MSG_SYNC, SYNC_STEP2]) + _write_varuint(len(update)) + update


def encode_sync_update(update: bytes) -> bytes:
    """Encode a y-websocket sync update message."""
    return bytes([MSG_SYNC, SYNC_UPDATE]) + _write_varuint(len(update)) + update


def extract_yjs_update(data: bytes) -> Optional[bytes]:
    """
    Extract the Yjs update bytes from a y-websocket protocol message.

    ONLY returns bytes for SYNC_UPDATE (type 2) messages — these are
    actual user edits. Sync step 1 (state vector request), sync step 2
    (initial state exchange), and awareness messages are all skipped.
    """
    if not data or len(data) < 3:
        return None

    msg_type = data[0]
    if msg_type != MSG_SYNC:
        return None  # awareness or other message, skip

    sync_type = data[1]
    if sync_type != SYNC_UPDATE:
        return None  # only count actual document updates (type 2)

    # Read varuint-prefixed update bytes
    try:
        length, offset = _read_varuint(data, 2)
        if offset + length <= len(data):
            return data[offset:offset + length]
    except Exception:
        pass

    return None


def extract_any_yjs_update(data: bytes) -> Optional[bytes]:
    """
    Extract Yjs update bytes from sync step 2 or sync update messages.

    Used by apply_update to keep the server-side Y.Doc in sync
    (including initial state from sync step 2).
    Does NOT count as user operations.
    """
    if not data or len(data) < 3:
        return None

    msg_type = data[0]
    if msg_type != MSG_SYNC:
        return None

    sync_type = data[1]
    if sync_type not in (SYNC_STEP2, SYNC_UPDATE):
        return None

    try:
        length, offset = _read_varuint(data, 2)
        if offset + length <= len(data):
            return data[offset:offset + length]
    except Exception:
        pass

    return None


class YjsUpdateType(Enum):
    """Types of Yjs operations."""
    INSERT = "insert"
    DELETE = "delete"
    FORMAT = "format"
    UNKNOWN = "unknown"


class YjsParser:
    """Parser for Yjs CRDT updates with per-document Y.Doc tracking."""

    def __init__(self):
        """Initialize Yjs parser with per-document document store."""
        self._docs: dict[str, ypy.YDoc] = {}
        self._texts: dict[str, ypy.YText] = {}

        if not HAS_YPY:
            logger.warning(
                "y-py not installed. Install with: pip install y-py. "
                "Falling back to content string extraction."
            )

    def _get_or_create_doc(self, doc_id: str) -> tuple:
        """Get or create a Y.Doc for a specific document ID."""
        if doc_id not in self._docs:
            doc = ypy.YDoc()
            text = doc.get_text("monaco")
            self._docs[doc_id] = doc
            self._texts[doc_id] = text
            logger.info(f"Created Yjs YDoc for document: {doc_id}")
        return self._docs[doc_id], self._texts[doc_id]

    def apply_update(self, doc_id: str, raw_ws_data: bytes) -> str:
        """
        Parse y-websocket protocol message and apply Yjs update if present.

        Applies BOTH sync step 2 and sync update messages to keep
        the server-side Y.Doc in sync with the clients.

        Args:
            doc_id: Document identifier
            raw_ws_data: Raw binary WebSocket message (y-websocket protocol)

        Returns:
            Current plain text after update, or empty string
        """
        if not HAS_YPY:
            return ""

        # Extract Yjs update from either sync step 2 or update messages
        update = extract_any_yjs_update(raw_ws_data)
        if update is None:
            return self.get_document_text(doc_id)

        try:
            doc, text = self._get_or_create_doc(doc_id)
            ypy.apply_update(doc, update)
            content = str(text)
            if content:
                logger.debug(f"Y.Doc for {doc_id}: {len(content)} chars")
            return content
        except Exception as e:
            logger.warning(f"Failed to apply Yjs update for {doc_id} ({len(update)} bytes): {e}")
            return self.get_document_text(doc_id)

    def handle_sync_step1(self, doc_id: str, raw_data: bytes) -> list[bytes]:
        """
        Handle incoming sync step 1: client sends its state vector.

        Returns list of y-websocket messages to send back:
          1. Sync step 2 with diff update for the client
          2. Sync step 1 with our state vector (to request client's state)
        """
        if not HAS_YPY:
            return []

        doc, text = self._get_or_create_doc(doc_id)

        # Extract client's state vector from the message
        # Format: [0, 0, varuint(len), state_vector_bytes...]
        try:
            sv_len, offset = _read_varuint(raw_data, 2)
            client_sv = raw_data[offset:offset + sv_len]
        except Exception as e:
            logger.warning(f"Failed to parse sync step 1 for {doc_id}: {e}")
            client_sv = b''

        responses = []

        # 1. Sync step 2: diff between our state and client's state vector
        try:
            if client_sv:
                update = ypy.encode_state_as_update(doc, client_sv)
            else:
                update = ypy.encode_state_as_update(doc)
            responses.append(encode_sync_step2(update))
            logger.debug(f"Sync step 2 for {doc_id}: {len(update)} byte update")
        except Exception as e:
            logger.warning(f"Failed to encode state update for {doc_id}: {e}")

        # 2. Sync step 1: send our state vector so client sends us theirs
        try:
            our_sv = ypy.encode_state_vector(doc)
            msg = bytes([MSG_SYNC, SYNC_STEP1]) + _write_varuint(len(our_sv)) + our_sv
            responses.append(msg)
            logger.debug(f"Sync step 1 reply for {doc_id}: {len(our_sv)} byte SV")
        except Exception as e:
            logger.warning(f"Failed to encode state vector for {doc_id}: {e}")

        return responses

    def handle_sync_step2(self, doc_id: str, raw_data: bytes) -> str:
        """
        Handle incoming sync step 2: client sends state as an update.
        Returns current document text after applying.
        """
        return self.apply_update(doc_id, raw_data)

    def handle_sync_update(self, doc_id: str, raw_data: bytes) -> str:
        """
        Handle incoming sync update: incremental edit from a client.
        Returns current document text after applying.
        """
        return self.apply_update(doc_id, raw_data)

    def get_document_text(self, doc_id: str) -> str:
        """
        Get current text content for a specific document.

        Args:
            doc_id: Document identifier

        Returns:
            Current plain text or empty string if unavailable
        """
        if not HAS_YPY or doc_id not in self._texts:
            return ""

        try:
            return str(self._texts[doc_id])
        except Exception as e:
            logger.error(f"Failed to get Yjs text for {doc_id}: {e}")
            return ""

    def get_current_text(self) -> str:
        """Legacy method — returns empty. Use get_document_text(doc_id) instead."""
        return ""

    def reset_document(self, doc_id: str = None) -> None:
        """Reset a specific document or all documents."""
        if doc_id:
            self._docs.pop(doc_id, None)
            self._texts.pop(doc_id, None)
            logger.info(f"Reset Yjs document: {doc_id}")
        else:
            self._docs.clear()
            self._texts.clear()
            logger.info("Reset all Yjs documents")

    @staticmethod
    def estimate_operation_count(update: bytes) -> int:
        """Estimate number of operations in Yjs update."""
        if not update or len(update) == 0:
            return 0
        try:
            estimated_ops = max(1, len(update) // 10)
            return estimated_ops
        except Exception as e:
            logger.error(f"Failed to estimate operation count: {e}")
            return 0

    @staticmethod
    def analyze_update(update: bytes) -> dict:
        """Analyze Yjs update structure."""
        analysis = {
            "size": len(update),
            "estimated_ops": YjsParser.estimate_operation_count(update),
            "type": YjsUpdateType.UNKNOWN,
            "has_content": len(update) > 5,
        }
        return analysis


# Global instance
_parser_instance: Optional[YjsParser] = None


def get_yjs_parser() -> YjsParser:
    """Get or create global Yjs parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = YjsParser()
    return _parser_instance


def extract_text_from_update(update: bytes) -> str:
    """Legacy convenience function."""
    return ""


def count_operations(update: bytes) -> int:
    """Count operations in Yjs update (estimated)."""
    return YjsParser.estimate_operation_count(update)
