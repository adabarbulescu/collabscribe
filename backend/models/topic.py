"""
Data models for topic modeling analysis.
"""

from __future__ import annotations

from pydantic import BaseModel


class TopicKeyword(BaseModel):
    """A keyword associated with a topic."""
    word: str
    weight: float


class Topic(BaseModel):
    """Represents a single topic extracted from document."""
    topic_id: int
    label: str
    keywords: list[TopicKeyword]
    proportion: float  # Proportion of document belonging to this topic (0-1)


class TopicModelingResponse(BaseModel):
    """Response for topic modeling analysis."""
    document_id: str
    topics: list[Topic]
    dominant_topic: int
    coherence_score: float = 0.0
    method: str = "NMF"  # NMF or LDA
