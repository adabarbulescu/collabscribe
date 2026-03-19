"""
Analytics service: compute and cache NLP-powered document metrics.

Covers basic metrics, readability, NER, sentiment, keywords, vocabulary, and
math content analysis. Results are cached in-memory (process-local dict) and
persisted to the document_analytics PostgreSQL table.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid5, NAMESPACE_URL

import asyncpg

logger = logging.getLogger("collabscribe.services.analytics")

# In-memory cache: content_hash → analytics result dict
_analytics_cache: dict[str, dict] = {}
_CACHE_MAX_SIZE = 500


class AnalyticsService:
    """Stateless service; instantiated per-request with the connection pool."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_analytics(self, doc_id: str, content: str) -> dict:
        """Return cached analytics if content is unchanged, else compute fresh."""
        content_hash = self._hash_content(content)

        # Memory cache check
        if content_hash in _analytics_cache:
            logger.debug("Cache hit (memory) for %s hash=%s", doc_id, content_hash[:8])
            cached = _analytics_cache[content_hash].copy()
            cached["cached"] = True
            return cached

        # DB cache check
        db_result = await self._load_from_db(content_hash)
        if db_result is not None:
            logger.debug("Cache hit (DB) for %s hash=%s", doc_id, content_hash[:8])
            _analytics_cache[content_hash] = db_result
            db_result["cached"] = True
            return db_result

        # Compute fresh
        result = self._compute_all(doc_id, content, content_hash)
        result["cached"] = False

        # Persist
        await self._persist_analytics(doc_id, content_hash, result)
        self._memory_cache_put(content_hash, result)

        return result

    async def get_insights(self, doc_id: str, limit: int = 60) -> dict:
        """Return temporal insights based on saved document versions."""
        capped_limit = max(1, min(limit, 200))
        document_id = await self._resolve_document_id(doc_id)
        if document_id is None:
            return {
                "document_id": doc_id,
                "timeline": [],
                "stats": self._empty_insights_stats(),
                "live_tracking": self._get_live_tracking(doc_id),
            }

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT version_number, created_at, content
                FROM document_versions
                WHERE document_id = $1
                ORDER BY version_number ASC
                LIMIT $2
                """,
                document_id,
                capped_limit,
            )

        timeline = []
        for row in rows:
            content = row["content"] or ""
            stripped = self._strip_markdown(content)
            basic = self._compute_basic_metrics(content, stripped)
            readability = self._compute_readability(stripped)
            timeline.append(
                {
                    "version_number": row["version_number"],
                    "created_at": row["created_at"],
                    "word_count": basic["word_count"],
                    "char_count": basic["char_count"],
                    "sentence_count": basic["sentence_count"],
                    "readability_score": readability.get("flesch_reading_ease") if readability else None,
                }
            )

        return {
            "document_id": doc_id,
            "timeline": timeline,
            "stats": self._compute_insights_stats(timeline),
            "live_tracking": self._get_live_tracking(doc_id),
        }

    # ------------------------------------------------------------------
    # Computation orchestrator
    # ------------------------------------------------------------------

    def _compute_all(self, doc_id: str, content: str, content_hash: str) -> dict:
        """Orchestrate all analytics computations for a document.

        Strips markdown, runs spaCy NLP if word count >= 10, then computes
        basic metrics, readability, NER, sentiment, keywords, vocabulary,
        math analysis, sentence lengths, and POS mix.
        """
        stripped = self._strip_markdown(content)
        basic = self._compute_basic_metrics(content, stripped)
        doc = self._get_doc(stripped) if basic["word_count"] >= 10 else None
        result: dict = {
            "document_id": doc_id,
            "content_hash": content_hash,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "basic_metrics": basic,
            "readability": self._compute_readability(stripped),
            "ner": self._compute_ner(stripped, doc),
            "sentiment": self._compute_sentiment(stripped),
            "keywords": self._compute_keywords(stripped),
            "vocabulary": self._compute_vocabulary(stripped, doc),
            "math_analysis": self._compute_math_analysis(content),
            "sentence_lengths": self._compute_sentence_length_distribution(doc),
            "pos_mix": self._compute_pos_mix(doc),
        }
        return result

    # ------------------------------------------------------------------
    # Basic metrics (Step 3)
    # ------------------------------------------------------------------

    def _compute_basic_metrics(self, raw: str, stripped: str) -> dict:
        """Calculate word/char/sentence/paragraph counts and reading time."""
        words = stripped.split() if stripped.strip() else []
        word_count = len(words)
        sentences = re.findall(r"[^.!?]*[.!?]+(?:\s|$)", stripped)
        sentence_count = max(len(sentences), 1 if word_count > 0 else 0)
        paragraphs = [p for p in raw.split("\n\n") if p.strip()]
        return {
            "word_count": word_count,
            "char_count": len(raw),
            "char_count_no_spaces": len(raw.replace(" ", "").replace("\n", "").replace("\t", "")),
            "paragraph_count": len(paragraphs),
            "sentence_count": sentence_count,
            "avg_sentence_length": round(word_count / sentence_count, 1) if sentence_count else 0,
            "reading_time_minutes": round(word_count / 200, 2),
            "line_count": raw.count("\n") + 1,
        }

    # ------------------------------------------------------------------
    # Readability (Step 4)
    # ------------------------------------------------------------------

    @staticmethod
    def _count_syllables(word: str) -> int:
        """Estimate syllable count using a simple vowel-group heuristic."""
        word = word.lower().rstrip("e")
        if not word:
            return 1
        count = len(re.findall(r"[aeiouy]+", word))
        return max(count, 1)

    def _flesch_scores(self, text: str) -> tuple[float, float]:
        """Compute Flesch Reading Ease and Flesch-Kincaid Grade Level."""
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        words = text.split()
        total_words = len(words)
        total_sentences = max(len(sentences), 1)
        total_syllables = sum(self._count_syllables(w) for w in words)

        # Flesch Reading Ease = 206.835 - 1.015*(words/sentences) - 84.6*(syllables/words)
        fre = 206.835 - 1.015 * (total_words / total_sentences) - 84.6 * (total_syllables / total_words)
        # Flesch-Kincaid Grade = 0.39*(words/sentences) + 11.8*(syllables/words) - 15.59
        fkg = 0.39 * (total_words / total_sentences) + 11.8 * (total_syllables / total_words) - 15.59

        return round(fre, 1), round(fkg, 1)

    def _compute_readability(self, stripped: str) -> Optional[dict]:
        words = stripped.split()
        if len(words) < 30:
            return None
        try:
            fre, fkg = self._flesch_scores(stripped)

            if fre >= 90:
                label, color = "Very Easy (5th grade)", "green"
            elif fre >= 80:
                label, color = "Easy (6th grade)", "green"
            elif fre >= 70:
                label, color = "Fairly Easy (7th grade)", "green"
            elif fre >= 60:
                label, color = "Standard (8-9th grade)", "yellow"
            elif fre >= 50:
                label, color = "Fairly Difficult (10-12th grade)", "yellow"
            elif fre >= 30:
                label, color = "Difficult (College)", "red"
            else:
                label, color = "Very Difficult (Graduate)", "red"

            tooltip = (
                f"Flesch Reading Ease: {fre}/100. "
                f"Flesch-Kincaid Grade Level: {fkg}. "
                "Higher ease scores indicate more readable text."
            )
            return {
                "flesch_reading_ease": fre,
                "flesch_kincaid_grade": fkg,
                "label": label,
                "color": color,
                "tooltip": tooltip,
            }
        except Exception as exc:
            logger.warning("Readability computation failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Named Entity Recognition (Step 6)
    # ------------------------------------------------------------------

    def _compute_ner(self, stripped: str, doc=None) -> Optional[dict]:
        """Extract named entities using spaCy NER, grouped by category."""
        words = stripped.split()
        if len(words) < 10:
            return None
        try:
            if doc is None:
                doc = self._get_doc(stripped)
            if doc is None:
                return None

            ENTITY_DISPLAY = {
                "PERSON": "People",
                "ORG": "Organizations",
                "GPE": "Places",
                "DATE": "Dates",
                "CARDINAL": "Numbers",
                "NORP": "Groups",
                "EVENT": "Events",
                "WORK_OF_ART": "Works",
                "LAW": "Laws",
                "LANGUAGE": "Languages",
            }

            entity_counts: dict[str, Counter] = defaultdict(Counter)
            for ent in doc.ents:
                if ent.label_ in ENTITY_DISPLAY:
                    entity_counts[ent.label_][ent.text.strip()] += 1

            groups = []
            for label, counter in entity_counts.items():
                if not counter:
                    continue
                top = counter.most_common(20)
                groups.append(
                    {
                        "label": label,
                        "display_name": ENTITY_DISPLAY.get(label, label),
                        "entities": [{"text": t, "count": c} for t, c in top],
                    }
                )

            groups.sort(key=lambda g: sum(e["count"] for e in g["entities"]), reverse=True)
            total = sum(sum(e["count"] for e in g["entities"]) for g in groups)
            return {"entity_groups": groups, "total_entities": total}
        except Exception as exc:
            logger.warning("NER computation failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Sentiment Analysis (Step 7)
    # ------------------------------------------------------------------

    def _compute_sentiment(self, stripped: str) -> Optional[dict]:
        """Analyse polarity (-1..+1) and subjectivity (0..1) via TextBlob."""
        words = stripped.split()
        if len(words) < 20:
            return None
        try:
            from textblob import TextBlob

            blob = TextBlob(stripped[:10_000])
            polarity = round(blob.sentiment.polarity, 3)
            subjectivity = round(blob.sentiment.subjectivity, 3)

            p_label = "Positive" if polarity > 0.1 else ("Negative" if polarity < -0.1 else "Neutral")
            s_label = (
                "Objective" if subjectivity < 0.3 else ("Subjective" if subjectivity > 0.6 else "Mixed")
            )

            if subjectivity < 0.3 and -0.1 <= polarity <= 0.1:
                interpretation = "Typical academic writing: objective and neutral tone."
            elif subjectivity > 0.5:
                interpretation = "Subjective tone detected — consider more formal language for academic work."
            elif polarity < -0.2:
                interpretation = "Slightly negative tone — common in critical analysis sections."
            else:
                interpretation = f"{p_label} tone with {s_label.lower()} writing style."

            return {
                "polarity": polarity,
                "subjectivity": subjectivity,
                "polarity_label": p_label,
                "subjectivity_label": s_label,
                "interpretation": interpretation,
            }
        except Exception as exc:
            logger.warning("Sentiment analysis failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Keyword Extraction via TF-IDF (Step 8)
    # ------------------------------------------------------------------

    def _compute_keywords(self, stripped: str) -> Optional[list[dict]]:
        """Extract top keywords using TF-IDF scoring across sentences."""
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", stripped) if len(s.strip()) > 10]
        if len(sentences) < 3:
            return None
        try:
            import numpy as np
            from sklearn.feature_extraction.text import TfidfVectorizer

            EXTRA_STOP = {
                "also",
                "however",
                "therefore",
                "thus",
                "furthermore",
                "moreover",
                "whereas",
                "et",
                "al",
                "fig",
                "figure",
                "table",
                "section",
                "example",
                "note",
                "see",
                "using",
                "used",
            }

            vectorizer = TfidfVectorizer(
                stop_words="english",
                ngram_range=(1, 2),
                max_features=200,
                min_df=1,
                max_df=0.85,
                sublinear_tf=True,
                strip_accents="unicode",
            )

            tfidf_matrix = vectorizer.fit_transform(sentences)
            feature_names = vectorizer.get_feature_names_out()
            scores = np.array(tfidf_matrix.sum(axis=0)).flatten()

            keyword_scores = [
                (feature_names[i], float(scores[i]))
                for i in range(len(feature_names))
                if not feature_names[i].replace(".", "").isdigit()
                and len(feature_names[i]) > 2
                and feature_names[i] not in EXTRA_STOP
            ]

            keyword_scores.sort(key=lambda x: x[1], reverse=True)
            top = keyword_scores[:15]
            if not top:
                return None

            max_score = top[0][1]
            return [
                {"term": term, "score": round(score / max_score * 100, 1)} for term, score in top
            ]
        except Exception as exc:
            logger.warning("Keyword extraction failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Vocabulary Analysis (Step 9)
    # ------------------------------------------------------------------

    def _compute_vocabulary(self, stripped: str, doc=None) -> Optional[dict]:
        """Calculate type-token ratio, lexical density, and top words."""
        words = stripped.split()
        if len(words) < 20:
            return None
        try:
            if doc is None:
                doc = self._get_doc(stripped)
            if doc is None:
                return None

            CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV", "PROPN"}
            AUX_VERBS = {
                "be",
                "have",
                "do",
                "will",
                "would",
                "shall",
                "should",
                "may",
                "might",
                "can",
                "could",
                "must",
            }

            all_lemmas: list[str] = []
            content_lemmas: list[str] = []

            for token in doc:
                if token.is_punct or token.is_space or token.is_stop:
                    continue
                lemma = token.lemma_.lower()
                if len(lemma) < 2:
                    continue
                all_lemmas.append(lemma)
                if token.pos_ in CONTENT_POS and lemma not in AUX_VERBS:
                    content_lemmas.append(lemma)

            total_tokens = len(all_lemmas)
            if total_tokens == 0:
                return None

            unique_types = len(set(all_lemmas))
            ttr = round(unique_types / total_tokens, 4)
            lexical_density = round(len(content_lemmas) / total_tokens, 4)

            if ttr > 0.6:
                ttr_label = "Rich vocabulary"
            elif ttr > 0.4:
                ttr_label = "Average vocabulary"
            else:
                ttr_label = "Repetitive vocabulary"

            freq = Counter(content_lemmas).most_common(10)

            return {
                "type_token_ratio": ttr,
                "ttr_label": ttr_label,
                "lexical_density": lexical_density,
                "unique_words": unique_types,
                "total_words_analyzed": total_tokens,
                "top_words": [{"word": w, "count": c} for w, c in freq],
            }
        except Exception as exc:
            logger.warning("Vocabulary analysis failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Sentence Length Distribution (Phase 2)
    # ------------------------------------------------------------------

    def _compute_sentence_length_distribution(self, doc) -> Optional[dict]:
        """Bin sentence lengths into 8 buckets and compute summary stats."""
        if doc is None:
            return None
        sentence_lengths = []
        for sent in doc.sents:
            length = sum(1 for token in sent if not token.is_space and not token.is_punct)
            if length > 0:
                sentence_lengths.append(length)

        if len(sentence_lengths) < 2:
            return None

        bins = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 25), (26, 30), (31, 40), (41, 1000)]
        labels = ["1-5", "6-10", "11-15", "16-20", "21-25", "26-30", "31-40", "41+"]
        counts = [0 for _ in bins]

        for length in sentence_lengths:
            for i, (low, high) in enumerate(bins):
                if low <= length <= high:
                    counts[i] += 1
                    break

        total = len(sentence_lengths)
        avg = round(sum(sentence_lengths) / total, 1)
        med = round(float(statistics.median(sentence_lengths)), 1)
        max_len = max(sentence_lengths)

        bin_results = []
        for label, count in zip(labels, counts):
            percent = round((count / total) * 100, 1)
            bin_results.append({"label": label, "count": count, "percent": percent})

        return {
            "total_sentences": total,
            "average": avg,
            "median": med,
            "max_length": max_len,
            "bins": bin_results,
        }

    # ------------------------------------------------------------------
    # POS Mix (Phase 2)
    # ------------------------------------------------------------------

    def _compute_pos_mix(self, doc) -> Optional[dict]:
        """Count part-of-speech tags and return top 8 with percentages."""
        if doc is None:
            return None

        counts = Counter()
        for token in doc:
            if token.is_space or token.is_punct:
                continue
            if token.pos_:
                counts[token.pos_] += 1

        total = sum(counts.values())
        if total < 10:
            return None

        display = {
            "NOUN": "Nouns",
            "PROPN": "Proper Nouns",
            "VERB": "Verbs",
            "ADJ": "Adjectives",
            "ADV": "Adverbs",
            "PRON": "Pronouns",
            "ADP": "Prepositions",
            "DET": "Determiners",
            "AUX": "Auxiliaries",
            "CCONJ": "Conjunctions",
            "SCONJ": "Subordinators",
            "NUM": "Numbers",
            "PART": "Particles",
            "INTJ": "Interjections",
            "SYM": "Symbols",
            "X": "Other",
        }

        top = counts.most_common(8)
        top_total = sum(count for _, count in top)
        results = [
            {
                "tag": tag,
                "display_name": display.get(tag, tag),
                "count": count,
                "percent": round((count / total) * 100, 1),
            }
            for tag, count in top
        ]

        other_count = total - top_total
        if other_count > 0:
            results.append(
                {
                    "tag": "OTHER",
                    "display_name": "Other",
                    "count": other_count,
                    "percent": round((other_count / total) * 100, 1),
                }
            )

        return {"total_tokens": total, "tags": results}

    # ------------------------------------------------------------------
    # Math Content Analysis (Step 10)
    # ------------------------------------------------------------------

    def _compute_math_analysis(self, content: str) -> dict:
        """Parse LaTeX math delimiters. Process block math first to avoid double-counting."""
        block_pattern = r"\$\$([\s\S]+?)\$\$"
        block_matches = re.findall(block_pattern, content)
        content_without_block = re.sub(block_pattern, " BLOCK_MATH_PLACEHOLDER ", content)

        inline_pattern = r"(?<!\$)\$(?!\$)([^$\n]+?)(?<!\$)\$(?!\$)"
        inline_matches = re.findall(inline_pattern, content_without_block)

        STRUCTURES = {
            "fractions": r"\\frac\{",
            "integrals": r"\\int(?:_|\^|[\s{])",
            "summations": r"\\sum(?:_|\^|[\s{])",
            "matrices": r"\\begin\{(?:matrix|pmatrix|bmatrix|vmatrix|Vmatrix)\}",
            "limits": r"\\lim(?:_|\^|[\s{])",
            "derivatives": r"\\(?:partial|nabla|frac\{d)",
            "square_roots": r"\\sqrt\{",
            "exponents": r"\^\{",
        }

        all_math = " ".join(block_matches + inline_matches)
        detected: dict[str, int] = {}
        for name, pattern in STRUCTURES.items():
            count = len(re.findall(pattern, all_math))
            if count > 0:
                detected[name] = count

        # Word count for density (prose without math)
        prose = re.sub(block_pattern, "", content)
        prose = re.sub(inline_pattern, "", prose)
        word_count = len(prose.split())

        inline_count = len(inline_matches)
        block_count = len(block_matches)
        total = inline_count + block_count
        density = round((total / word_count * 1000), 2) if word_count > 0 else 0

        if density == 0:
            density_label = "No math"
        elif density < 5:
            density_label = "Low (mostly prose)"
        elif density < 20:
            density_label = "Moderate (mixed content)"
        elif density < 50:
            density_label = "High (math-heavy)"
        else:
            density_label = "Very High (primarily mathematical)"

        return {
            "inline_count": inline_count,
            "block_count": block_count,
            "total_equations": total,
            "math_density": density,
            "density_label": density_label,
            "detected_structures": detected,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_content(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Remove markdown and LaTeX syntax to extract prose text."""
        text = re.sub(r"```[\s\S]*?```", " ", text)
        text = re.sub(r"`[^`]+`", " ", text)
        text = re.sub(r"\$\$[\s\S]*?\$\$", " ", text)
        text = re.sub(r"\$[^$\n]+\$", " ", text)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\*([^*]+)\*", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"^[-*+]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
        return text

    def _get_doc(self, stripped: str):
        if not stripped.strip():
            return None
        try:
            from services.nlp_pipeline import get_nlp

            nlp = get_nlp()
            return nlp(stripped[:50_000])
        except Exception as exc:
            logger.warning("spaCy processing failed: %s", exc)
            return None

    async def _resolve_document_id(self, doc_id: str) -> Optional[UUID]:
        """Convert a short doc_id string to the internal UUID primary key."""
        if not doc_id:
            return None
        doc_uuid = uuid5(NAMESPACE_URL, doc_id) if not self._is_valid_uuid(doc_id) else UUID(doc_id)
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchval(
                    "SELECT id FROM documents WHERE id = $1",
                    doc_uuid,
                )
        except Exception as exc:
            logger.warning("Failed to resolve document id %s: %s", doc_id, exc)
            return None

    @staticmethod
    def _is_valid_uuid(value: str) -> bool:
        try:
            UUID(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def _empty_insights_stats() -> dict:
        return {
            "total_versions": 0,
            "start_time": None,
            "end_time": None,
            "net_words": 0,
            "avg_wpm": 0,
            "last_version_number": None,
        }

    def _compute_insights_stats(self, timeline: list[dict]) -> dict:
        if not timeline:
            return self._empty_insights_stats()

        start = timeline[0]["created_at"]
        end = timeline[-1]["created_at"]
        start_words = timeline[0]["word_count"]
        end_words = timeline[-1]["word_count"]
        net_words = end_words - start_words
        duration_minutes = (end - start).total_seconds() / 60 if end and start else 0
        avg_wpm = round((net_words / duration_minutes), 2) if duration_minutes > 0 else 0

        return {
            "total_versions": len(timeline),
            "start_time": start,
            "end_time": end,
            "net_words": net_words,
            "avg_wpm": avg_wpm,
            "last_version_number": timeline[-1]["version_number"],
        }

    @staticmethod
    def _get_live_tracking(doc_id: str) -> Optional[dict]:
        try:
            from utils import get_tracking_manager

            tracking_manager = get_tracking_manager()
            return tracking_manager.get_tracker_status(doc_id)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Cache persistence
    # ------------------------------------------------------------------

    async def _load_from_db(self, content_hash: str) -> Optional[dict]:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT analytics_data, computed_at FROM document_analytics "
                    "WHERE content_hash = $1 LIMIT 1",
                    content_hash,
                )
                if row:
                    result = json.loads(row["analytics_data"])
                    result["computed_at"] = row["computed_at"].isoformat()
                    return result
        except Exception as exc:
            logger.warning("Failed to load analytics from DB: %s", exc)
        return None

    async def _persist_analytics(self, doc_id: str, content_hash: str, data: dict) -> None:
        """Upsert analytics result into document_analytics table."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO document_analytics
                        (id, document_id, content_hash, analytics_data, computed_at)
                    VALUES (gen_random_uuid(), $1, $2, $3::jsonb, NOW())
                    ON CONFLICT (content_hash) DO UPDATE SET
                        analytics_data = EXCLUDED.analytics_data,
                        computed_at = NOW()
                    """,
                    doc_id,
                    content_hash,
                    json.dumps(data, default=str),
                )
        except Exception as exc:
            logger.warning("Failed to persist analytics to DB: %s", exc)

    def _memory_cache_put(self, content_hash: str, result: dict) -> None:
        """Store result in the in-memory LRU cache (FIFO, max 500 entries)."""
        if len(_analytics_cache) >= _CACHE_MAX_SIZE:
            # Evict oldest entry
            oldest_key = next(iter(_analytics_cache))
            del _analytics_cache[oldest_key]
        _analytics_cache[content_hash] = result
