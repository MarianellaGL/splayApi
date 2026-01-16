"""
Spec Cache - Caches compiled GameSpecs by rules hash.

The cache:
- Uses content hash as key
- Stores on local disk (JSON/pickle)
- No database required
- Specs can be reused across sessions
- Cache is the ONLY persistence in the system

Design decisions:
- Simple file-based storage
- Hash includes rules text + compiler version
- Cache is optional (can always recompile)
"""

from __future__ import annotations
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..spec_schema import GameSpec


@dataclass
class CacheEntry:
    """
    A cached spec entry.
    """
    spec_hash: str
    rules_hash: str
    compiler_version: str
    spec: GameSpec
    metadata: dict[str, Any] = field(default_factory=dict)

    # Cache metadata
    created_at: float = 0.0
    last_accessed: float = 0.0
    access_count: int = 0


class SpecCache:
    """
    File-based cache for compiled GameSpecs.

    Usage:
        cache = SpecCache(cache_dir="~/.splay/cache")

        # Check if rules are cached
        spec = cache.get(rules_text)
        if spec:
            return spec

        # Compile and cache
        spec = compile(rules_text)
        cache.put(rules_text, spec)
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        compiler_version: str = "1.0.0",
    ):
        if cache_dir is None:
            cache_dir = Path.home() / ".splay" / "cache"
        self.cache_dir = Path(cache_dir)
        self.compiler_version = compiler_version

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, rules_text: str) -> GameSpec | None:
        """
        Get cached spec for rules text.

        Returns None if not cached or cache is invalid.
        """
        rules_hash = self._hash_rules(rules_text)
        cache_key = self._make_cache_key(rules_hash)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            entry = self._load_entry(cache_path)
            if entry and entry.compiler_version == self.compiler_version:
                # Update access metadata
                import time
                entry.last_accessed = time.time()
                entry.access_count += 1
                self._save_entry(cache_path, entry)
                return entry.spec
        except Exception:
            # Invalid cache entry, delete it
            cache_path.unlink(missing_ok=True)

        return None

    def put(
        self,
        rules_text: str,
        spec: GameSpec,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Cache a compiled spec.
        """
        import time

        rules_hash = self._hash_rules(rules_text)
        cache_key = self._make_cache_key(rules_hash)
        cache_path = self._get_cache_path(cache_key)

        entry = CacheEntry(
            spec_hash=cache_key,
            rules_hash=rules_hash,
            compiler_version=self.compiler_version,
            spec=spec,
            metadata=metadata or {},
            created_at=time.time(),
            last_accessed=time.time(),
            access_count=1,
        )

        self._save_entry(cache_path, entry)

    def invalidate(self, rules_text: str):
        """
        Remove cached spec for rules text.
        """
        rules_hash = self._hash_rules(rules_text)
        cache_key = self._make_cache_key(rules_hash)
        cache_path = self._get_cache_path(cache_key)
        cache_path.unlink(missing_ok=True)

    def clear(self):
        """
        Clear entire cache.
        """
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def list_cached(self) -> list[str]:
        """
        List all cached spec hashes.
        """
        if not self.cache_dir.exists():
            return []

        return [
            f.stem for f in self.cache_dir.glob("*.json")
        ]

    def _hash_rules(self, rules_text: str) -> str:
        """
        Create hash of rules text.

        Uses SHA-256 truncated to 16 chars.
        """
        content = rules_text.encode("utf-8")
        return hashlib.sha256(content).hexdigest()[:16]

    def _make_cache_key(self, rules_hash: str) -> str:
        """
        Create cache key from rules hash and compiler version.
        """
        version_hash = hashlib.sha256(
            self.compiler_version.encode()
        ).hexdigest()[:8]
        return f"{rules_hash}_{version_hash}"

    def _get_cache_path(self, cache_key: str) -> Path:
        """
        Get file path for cache entry.
        """
        return self.cache_dir / f"{cache_key}.json"

    def _load_entry(self, path: Path) -> CacheEntry | None:
        """
        Load cache entry from file.

        STUB: Full implementation would deserialize GameSpec.
        For now, returns None (cache miss).
        """
        # STUB: Implement proper serialization
        return None

    def _save_entry(self, path: Path, entry: CacheEntry):
        """
        Save cache entry to file.

        STUB: Full implementation would serialize GameSpec.
        """
        # STUB: Implement proper serialization
        # For now, just create an empty file as marker
        metadata = {
            "spec_hash": entry.spec_hash,
            "rules_hash": entry.rules_hash,
            "compiler_version": entry.compiler_version,
            "created_at": entry.created_at,
            "game_id": entry.spec.game_id,
            "game_name": entry.spec.game_name,
        }
        with open(path, "w") as f:
            json.dump(metadata, f, indent=2)
