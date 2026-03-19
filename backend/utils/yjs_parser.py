"""
Yjs CRDT update parsing and text extraction helpers.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

try:
    import y_py as ypy

    HAS_YPY = True
except ImportError:
    HAS_YPY = False

logger = logging.getLogger(__name__)

MSG_SYNC = 0
MSG_AWARENESS = 1
SYNC_STEP1 = 0
SYNC_STEP2 = 1
SYNC_UPDATE = 2


def _read_varuint(data: bytes, offset: int) -> tuple[int, int]:
    """Read a variable-length unsigned integer."""
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
    """Encode a variable-length unsigned integer."""
    buf = bytearray()
    while value > 0x7F:
        buf.append((value & 0x7F) | 0x80)
        value >>= 7
    buf.append(value & 0x7F)
    return bytes(buf)


def encode_sync_step2(update: bytes) -> bytes:
    """Encode a sync step 2 message containing a Yjs update."""
    return bytes([MSG_SYNC, SYNC_STEP2]) + _write_varuint(len(update)) + update


def encode_sync_update(update: bytes) -> bytes:
    """Encode a sync update message."""
    return bytes([MSG_SYNC, SYNC_UPDATE]) + _write_varuint(len(update)) + update


def extract_yjs_update(data: bytes) -> Optional[bytes]:
    """Extract the Yjs update bytes from a sync update message."""
    if not data or len(data) < 3 or data[0] != MSG_SYNC or data[1] != SYNC_UPDATE:
        return None

    try:
        length, offset = _read_varuint(data, 2)
        if offset + length <= len(data):
            return data[offset : offset + length]
    except Exception:
        return None

    return None


def extract_any_yjs_update(data: bytes) -> Optional[bytes]:
    """Extract Yjs update bytes from sync step 2 or sync update messages."""
    if not data or len(data) < 3 or data[0] != MSG_SYNC:
        return None
    if data[1] not in (SYNC_STEP2, SYNC_UPDATE):
        return None

    try:
        length, offset = _read_varuint(data, 2)
        if offset + length <= len(data):
            return data[offset : offset + length]
    except Exception:
        return None

    return None


class YjsUpdateType(Enum):
    INSERT = "insert"
    DELETE = "delete"
    FORMAT = "format"
    UNKNOWN = "unknown"


class YjsParser:
    """Parser for Yjs CRDT updates with per-document Y.Doc tracking."""

    def __init__(self):
        self._docs: dict[str, "ypy.YDoc"] = {}
        self._texts: dict[str, "ypy.YText"] = {}

        if not HAS_YPY:
            logger.warning("y-py not installed; falling back to no-op parsing.")

    def _get_or_create_doc(self, doc_id: str) -> tuple["ypy.YDoc", "ypy.YText"]:
        if doc_id not in self._docs:
            doc = ypy.YDoc()
            text = doc.get_text("monaco")
            self._docs[doc_id] = doc
            self._texts[doc_id] = text
            logger.info("Created Yjs YDoc for document %s", doc_id)
        return self._docs[doc_id], self._texts[doc_id]

    def apply_binary_update(self, doc_id: str, update: bytes) -> str:
        """Apply a raw Yjs binary update for a document and return current text."""
        if not HAS_YPY or not update:
            return self.get_document_text(doc_id)

        try:
            doc, text = self._get_or_create_doc(doc_id)
            ypy.apply_update(doc, update)
            return str(text)
        except Exception as exc:
            logger.warning(
                "Failed to apply raw Yjs update for %s (%d bytes): %s",
                doc_id,
                len(update),
                exc,
            )
            return self.get_document_text(doc_id)

    def apply_update(self, doc_id: str, raw_ws_data: bytes) -> str:
        """Apply a y-websocket framed update for a document."""
        if not HAS_YPY:
            return ""

        update = extract_any_yjs_update(raw_ws_data)
        if update is None:
            return self.get_document_text(doc_id)
        return self.apply_binary_update(doc_id, update)

    def handle_sync_step1(self, doc_id: str, raw_data: bytes) -> list[bytes]:
        """Handle sync step 1 and return response frames."""
        if not HAS_YPY:
            return []

        doc, _ = self._get_or_create_doc(doc_id)

        try:
            sv_len, offset = _read_varuint(raw_data, 2)
            client_sv = raw_data[offset : offset + sv_len]
        except Exception as exc:
            logger.warning("Failed to parse sync step 1 for %s: %s", doc_id, exc)
            client_sv = b""

        responses = []

        try:
            update = ypy.encode_state_as_update(doc, client_sv) if client_sv else ypy.encode_state_as_update(doc)
            responses.append(encode_sync_step2(update))
        except Exception as exc:
            logger.warning("Failed to encode state update for %s: %s", doc_id, exc)

        try:
            our_sv = ypy.encode_state_vector(doc)
            responses.append(bytes([MSG_SYNC, SYNC_STEP1]) + _write_varuint(len(our_sv)) + our_sv)
        except Exception as exc:
            logger.warning("Failed to encode state vector for %s: %s", doc_id, exc)

        return responses

    def handle_sync_step2(self, doc_id: str, raw_data: bytes) -> str:
        return self.apply_update(doc_id, raw_data)

    def handle_sync_update(self, doc_id: str, raw_data: bytes) -> str:
        return self.apply_update(doc_id, raw_data)

    def get_document_text(self, doc_id: str) -> str:
        if not HAS_YPY or doc_id not in self._texts:
            return ""

        try:
            return str(self._texts[doc_id])
        except Exception as exc:
            logger.error("Failed to get Yjs text for %s: %s", doc_id, exc)
            return ""

    def get_current_text(self) -> str:
        return ""

    def reset_document(self, doc_id: str | None = None) -> None:
        if doc_id:
            self._docs.pop(doc_id, None)
            self._texts.pop(doc_id, None)
            logger.info("Reset Yjs document %s", doc_id)
            return

        self._docs.clear()
        self._texts.clear()
        logger.info("Reset all Yjs documents")

    @staticmethod
    def estimate_operation_count(update: bytes) -> int:
        if not update:
            return 0
        return max(1, len(update) // 10)

    @staticmethod
    def analyze_update(update: bytes) -> dict:
        return {
            "size": len(update),
            "estimated_ops": YjsParser.estimate_operation_count(update),
            "type": YjsUpdateType.UNKNOWN,
            "has_content": len(update) > 5,
        }


_parser_instance: Optional[YjsParser] = None


def get_yjs_parser() -> YjsParser:
    """Get or create the shared Yjs parser."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = YjsParser()
    return _parser_instance


def extract_text_from_update(update: bytes) -> str:
    """Compatibility shim used by tests; raw updates alone do not expose plain text here."""
    return ""


def count_operations(update: bytes) -> int:
    """Estimate operation count from update size."""
    return YjsParser.estimate_operation_count(update)
