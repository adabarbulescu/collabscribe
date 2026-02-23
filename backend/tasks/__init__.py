"""
Background tasks for collaborative editor.

Includes:
- Document snapshot scheduler
- Operation cleanup
- Database maintenance
"""

from .snapshot_scheduler import (
    SnapshotScheduler,
    get_snapshot_scheduler,
    snapshot_scheduler_lifespan,
)

__all__ = [
    "SnapshotScheduler",
    "get_snapshot_scheduler",
    "snapshot_scheduler_lifespan",
]
