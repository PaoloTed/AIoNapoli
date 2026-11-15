"""Document cache for scraper and LLM deduplication (06_agente_scraping.md §7.2)."""

from __future__ import annotations

import json
from pathlib import Path


class DocumentCache:
    """Manages document deduplication so identical documents do not trigger LLM calls."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._cache_dir = cache_dir
        self._memory_set: set[str] = set()
        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    def has(self, doc_hash: str) -> bool:
        if doc_hash in self._memory_set:
            return True
        if self._cache_dir is not None:
            f = self._cache_dir / f"{doc_hash}.json"
            return f.exists()
        return False

    def put(self, doc_hash: str, metadata: dict | None = None) -> None:
        self._memory_set.add(doc_hash)
        if self._cache_dir is not None:
            f = self._cache_dir / f"{doc_hash}.json"
            f.write_text(json.dumps(metadata or {"hash": doc_hash}), encoding="utf-8")
