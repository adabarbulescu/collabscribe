"""
Utility modules for collaborative editor backend.

Provides:
- Yjs CRDT text extraction
- Document snapshot management
- Operation tracking
"""

from .yjs_parser import (
    YjsParser,
    YjsUpdateType,
    get_yjs_parser,
    extract_text_from_update,
    count_operations,
)

from .operation_tracking import (
    DocumentOperationTracker,
    OperationTrackingManager,
    get_tracking_manager,
)

__all__ = [
    "YjsParser",
    "YjsUpdateType",
    "get_yjs_parser",
    "extract_text_from_update",
    "count_operations",
    "DocumentOperationTracker",
    "OperationTrackingManager",
    "get_tracking_manager",
]
