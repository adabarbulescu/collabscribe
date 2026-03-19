"""
Topic modeling service using scikit-learn NMF/LDA.
Extracts latent topics from document text.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.decomposition import NMF, LatentDirichletAllocation

logger = logging.getLogger("collabscribe.services.topic_modeling")


class TopicModelingService:
    """Service for extracting topics from documents."""

    def __init__(self):
        self.stop_words_extra = {
            "also", "however", "therefore", "thus", "furthermore", "moreover",
            "whereas", "et", "al", "fig", "figure", "table", "section",
            "example", "note", "see", "using", "used", "use", "based",
            "paper", "study", "research", "work", "approach", "method"
        }

    def extract_topics(
        self,
        content: str,
        n_topics: int = 5,
        method: str = "nmf",
        n_keywords: int = 8
    ) -> Optional[dict]:
        """
        Extract topics from document content.

        Args:
            content: Document text
            n_topics: Number of topics to extract (default: 5)
            method: "nmf" or "lda" (default: "nmf")
            n_keywords: Number of keywords per topic (default: 8)

        Returns:
            Dictionary with topics, keywords, and proportions, or None if extraction fails
        """
        # Strip markdown/LaTeX
        text = self._strip_markdown(content)
        
        # Need sufficient text for topic modeling
        words = text.split()
        if len(words) < 100:
            logger.info("Document too short for topic modeling (< 100 words)")
            return None

        try:
            if method.lower() == "lda":
                return self._extract_lda_topics(text, n_topics, n_keywords)
            else:
                return self._extract_nmf_topics(text, n_topics, n_keywords)
        except Exception as exc:
            logger.error(f"Topic extraction failed: {exc}")
            return None

    def _extract_nmf_topics(self, text: str, n_topics: int, n_keywords: int) -> dict:
        """Extract topics using Non-negative Matrix Factorization."""
        # Use TF-IDF for NMF with combined stop words
        from sklearn.feature_extraction import _stop_words
        stop_words_list = list(_stop_words.ENGLISH_STOP_WORDS | self.stop_words_extra)
        
        vectorizer = TfidfVectorizer(
            max_features=1000,
            min_df=1,
            max_df=1.0,
            stop_words=stop_words_list,
            ngram_range=(1, 2)
        )

        tfidf = vectorizer.fit_transform([text])
        feature_names = vectorizer.get_feature_names_out()
        
        # Check if we have enough features for the requested number of topics
        n_features = len(feature_names)
        if n_features < n_topics:
            logger.warning(f"Not enough features ({n_features}) for {n_topics} topics, reducing to {n_features}")
            n_topics = max(1, n_features)

        # NMF model - use random init for better stability with small datasets
        nmf = NMF(
            n_components=n_topics,
            random_state=42,
            init="random",
            max_iter=500
        )
        doc_topic = nmf.fit_transform(tfidf)

        # Extract topics and keywords
        topics = []
        for topic_idx, topic in enumerate(nmf.components_):
            # Get top keywords for this topic
            top_indices = topic.argsort()[-n_keywords:][::-1]
            keywords = []
            for idx in top_indices:
                keywords.append({
                    "word": feature_names[idx],
                    "weight": float(topic[idx])
                })

            # Normalize weights to 0-1 range within topic
            max_weight = max(kw["weight"] for kw in keywords)
            if max_weight > 0:
                for kw in keywords:
                    kw["weight"] = round(kw["weight"] / max_weight, 3)

            # Generate topic label from top 3 keywords
            label = ", ".join([kw["word"] for kw in keywords[:3]])

            topics.append({
                "topic_id": topic_idx,
                "label": label.title(),
                "keywords": keywords,
                "proportion": float(doc_topic[0][topic_idx])
            })

        # Normalize proportions to sum to 1.0
        total_prop = sum(t["proportion"] for t in topics)
        if total_prop > 0:
            for topic in topics:
                topic["proportion"] = round(topic["proportion"] / total_prop, 3)

        # Find dominant topic
        dominant_topic = max(range(len(topics)), key=lambda i: topics[i]["proportion"])

        return {
            "topics": topics,
            "dominant_topic": dominant_topic,
            "method": "NMF",
            "coherence_score": 0.0,  # Could compute coherence if needed
        }

    def _extract_lda_topics(self, text: str, n_topics: int, n_keywords: int) -> dict:
        """Extract topics using Latent Dirichlet Allocation."""
        # Use Count Vectorizer for LDA (works better with counts than TF-IDF)
        from sklearn.feature_extraction import _stop_words
        stop_words_list = list(_stop_words.ENGLISH_STOP_WORDS | self.stop_words_extra)
        
        vectorizer = CountVectorizer(
            max_features=1000,
            min_df=1,
            max_df=1.0,
            stop_words=stop_words_list,
            ngram_range=(1, 2)
        )

        counts = vectorizer.fit_transform([text])
        feature_names = vectorizer.get_feature_names_out()
        
        # Check if we have enough features for the requested number of topics
        n_features = len(feature_names)
        if n_features < n_topics:
            logger.warning(f"Not enough features ({n_features}) for {n_topics} topics, reducing to {n_features}")
            n_topics = max(1, n_features)

        # LDA model
        lda = LatentDirichletAllocation(
            n_components=n_topics,
            random_state=42,
            max_iter=500,
            learning_method="online"
        )
        doc_topic = lda.fit_transform(counts)

        # Extract topics and keywords
        topics = []
        for topic_idx, topic in enumerate(lda.components_):
            # Get top keywords for this topic
            top_indices = topic.argsort()[-n_keywords:][::-1]
            keywords = []
            for idx in top_indices:
                keywords.append({
                    "word": feature_names[idx],
                    "weight": float(topic[idx])
                })

            # Normalize weights
            max_weight = max(kw["weight"] for kw in keywords)
            if max_weight > 0:
                for kw in keywords:
                    kw["weight"] = round(kw["weight"] / max_weight, 3)

            # Generate topic label
            label = ", ".join([kw["word"] for kw in keywords[:3]])

            topics.append({
                "topic_id": topic_idx,
                "label": label.title(),
                "keywords": keywords,
                "proportion": float(doc_topic[0][topic_idx])
            })

        # Normalize proportions
        total_prop = sum(t["proportion"] for t in topics)
        if total_prop > 0:
            for topic in topics:
                topic["proportion"] = round(topic["proportion"] / total_prop, 3)

        # Find dominant topic
        dominant_topic = max(range(len(topics)), key=lambda i: topics[i]["proportion"])

        return {
            "topics": topics,
            "dominant_topic": dominant_topic,
            "method": "LDA",
            "coherence_score": 0.0,
        }

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
