"""
spaCy NLP pipeline singleton.

Initialized once at FastAPI startup via lifespan, reused across all requests.
The loaded nlp object is safe for concurrent use in an asyncio context since
each call creates a new Doc object; the model weights are read-only.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("collabscribe.services.nlp")

_nlp = None


def get_nlp():
    """Return the loaded spaCy pipeline. Raises RuntimeError if not initialized."""
    if _nlp is None:
        raise RuntimeError("NLP pipeline not initialized. Call init_nlp() at startup.")
    return _nlp


async def init_nlp() -> None:
    """Load spaCy model in a thread executor to avoid blocking the event loop."""
    global _nlp

    def _load():
        import spacy

        nlp = spacy.load("en_core_web_sm", disable=["parser"])
        nlp.add_pipe("sentencizer")
        nlp.max_length = 2_000_000
        return nlp

    loop = asyncio.get_event_loop()
    _nlp = await loop.run_in_executor(None, _load)
    logger.info("spaCy pipeline initialized: en_core_web_sm (parser disabled, sentencizer added)")
