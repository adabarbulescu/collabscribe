"""
Data models for version comparison and diff operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class VersionMetadata(BaseModel):
    """Metadata for a document version."""
    version_number: int
    created_at: datetime
    word_count: int
    char_count: int


class DiffChunk(BaseModel):
    """A chunk of text with diff operation."""
    operation: str  # 'equal', 'insert', 'delete'
    text: str


class AnalyticsDelta(BaseModel):
    """Delta between two versions' analytics."""
    metric: str
    old_value: float
    new_value: float
    delta: float
    percent_change: Optional[float] = None
    direction: str  # 'up', 'down', 'neutral'


class VersionComparisonResponse(BaseModel):
    """Response for version comparison."""
    document_id: str
    version1: VersionMetadata
    version2: VersionMetadata
    diff_chunks: list[DiffChunk]
    analytics_deltas: list[AnalyticsDelta]
    summary: dict[str, Any]
