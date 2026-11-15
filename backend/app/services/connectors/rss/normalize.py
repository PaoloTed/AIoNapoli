"""Document text normalization and deduplication hash (06_agente_scraping.md §7)."""

from __future__ import annotations

import hashlib
import re

_HTML_TAGS_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str | None) -> str:
    """Normalize body by removing HTML tags, carriage returns, and collapsing whitespace."""
    if not text:
        return ""
    # Strip HTML tags
    no_html = _HTML_TAGS_RE.sub(" ", text)
    # Fix whitespace before punctuation
    no_punct_space = re.sub(r"\s+([.,;:!?])", r"\1", no_html)
    # Normalize CRLF and consecutive whitespace
    normalized = _WHITESPACE_RE.sub(" ", no_punct_space).strip()
    return normalized


def compute_document_hash(normalized_text: str) -> str:
    """Compute 16-char SHA-256 hash on normalized body for model call deduplication."""
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()[:16]
