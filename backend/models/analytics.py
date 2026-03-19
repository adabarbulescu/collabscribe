"""Pydantic models for analytics API request/response."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AnalyticsRequest(BaseModel):
    content: str = Field(..., description="Document content to analyze")


class BasicMetrics(BaseModel):
    word_count: int = 0
    char_count: int = 0
    char_count_no_spaces: int = 0
    paragraph_count: int = 0
    sentence_count: int = 0
    avg_sentence_length: float = 0
    reading_time_minutes: float = 0
    line_count: int = 0


class ReadabilityMetrics(BaseModel):
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    label: str
    color: str
    tooltip: str


class EntityOccurrence(BaseModel):
    text: str
    count: int


class EntityGroup(BaseModel):
    label: str
    display_name: str
    entities: list[EntityOccurrence]


class NERResult(BaseModel):
    entity_groups: list[EntityGroup]
    total_entities: int


class SentimentResult(BaseModel):
    polarity: float
    subjectivity: float
    polarity_label: str
    subjectivity_label: str
    interpretation: str


class KeywordItem(BaseModel):
    term: str
    score: float


class WordFrequency(BaseModel):
    word: str
    count: int


class VocabularyResult(BaseModel):
    type_token_ratio: float
    ttr_label: str
    lexical_density: float
    unique_words: int
    total_words_analyzed: int
    top_words: list[WordFrequency]


class SentenceLengthBin(BaseModel):
    label: str
    count: int
    percent: float


class SentenceLengthDistribution(BaseModel):
    total_sentences: int
    average: float
    median: float
    max_length: int
    bins: list[SentenceLengthBin]


class PosMixItem(BaseModel):
    tag: str
    display_name: str
    count: int
    percent: float


class PosMixResult(BaseModel):
    total_tokens: int
    tags: list[PosMixItem]


class MathStructures(BaseModel):
    """Counts of detected LaTeX mathematical structures."""
    fractions: int = 0
    integrals: int = 0
    summations: int = 0
    matrices: int = 0
    limits: int = 0
    derivatives: int = 0
    square_roots: int = 0
    exponents: int = 0


class MathAnalysisResult(BaseModel):
    inline_count: int = 0
    block_count: int = 0
    total_equations: int = 0
    math_density: float = 0
    density_label: str = "No math"
    detected_structures: dict[str, int] = {}


class InsightsPoint(BaseModel):
    version_number: int
    created_at: datetime
    word_count: int
    char_count: int
    sentence_count: int
    readability_score: Optional[float] = None


class InsightsStats(BaseModel):
    total_versions: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    net_words: int
    avg_wpm: float
    last_version_number: Optional[int] = None


class InsightsResponse(BaseModel):
    document_id: str
    timeline: list[InsightsPoint]
    stats: InsightsStats
    live_tracking: Optional[dict] = None


class AnalyticsResponse(BaseModel):
    document_id: str
    content_hash: str
    cached: bool = False
    computed_at: str
    basic_metrics: BasicMetrics
    readability: Optional[ReadabilityMetrics] = None
    ner: Optional[NERResult] = None
    sentiment: Optional[SentimentResult] = None
    keywords: Optional[list[KeywordItem]] = None
    vocabulary: Optional[VocabularyResult] = None
    math_analysis: Optional[MathAnalysisResult] = None
    sentence_lengths: Optional[SentenceLengthDistribution] = None
    pos_mix: Optional[PosMixResult] = None
