"""
Analysis Cache & History Manager.

Thread-safe LRU cache for expensive computations and
persistent JSON history of analysis runs.
"""
import os
import json
import time
import hashlib
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CacheEntry:
    key: str
    data: Any
    created_at: float
    ttl_seconds: float
    hits: int = 0
    module: str = ""

    @property
    def is_expired(self) -> bool:
        return self.ttl_seconds > 0 and (time.time() - self.created_at) > self.ttl_seconds


@dataclass
class HistoryRecord:
    record_id: str
    module: str
    timestamp: str
    input_summary: Dict
    result_summary: Dict
    duration_seconds: float
    success: bool
    error_message: str = ""


class AnalysisCache:
    """Thread-safe LRU+TTL in-memory cache."""

    TTL = {"regression": 3600, "scenario": 3600, "financial": 1800, "default": 900}

    def __init__(self, max_size: int = 50):
        self._store: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self.max_size = max_size
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def _key(self, module: str, params: dict) -> str:
        try:
            raw = json.dumps(params, sort_keys=True, default=str)
        except Exception:
            raw = str(params)
        return f"{module}:{hashlib.md5(f'{module}:{raw}'.encode()).hexdigest()[:16]}"

    def get(self, module: str, params: dict) -> Optional[Any]:
        k = self._key(module, params)
        with self._lock:
            e = self._store.get(k)
            if e is None or e.is_expired:
                if e:
                    del self._store[k]
                self._stats["misses"] += 1
                return None
            e.hits += 1
            self._stats["hits"] += 1
            return e.data

    def set(self, module: str, params: dict, data: Any, ttl: Optional[float] = None) -> str:
        k = self._key(module, params)
        ttl = ttl or self.TTL.get(module, self.TTL["default"])
        with self._lock:
            if len(self._store) >= self.max_size:
                self._evict()
            self._store[k] = CacheEntry(k, data, time.time(), ttl, module=module)
        return k

    def _evict(self):
        expired = [k for k, e in self._store.items() if e.is_expired]
        for k in expired:
            del self._store[k]
            self._stats["evictions"] += 1
        if len(self._store) >= self.max_size:
            oldest = min(self._store, key=lambda k: self._store[k].created_at)
            del self._store[oldest]
            self._stats["evictions"] += 1

    def invalidate(self, module: Optional[str] = None):
        with self._lock:
            if module:
                for k in [k for k, e in self._store.items() if e.module == module]:
                    del self._store[k]
            else:
                self._store.clear()

    def get_stats(self) -> dict:
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            return {
                "total_entries": len(self._store),
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "evictions": self._stats["evictions"],
                "hit_rate_pct": round(self._stats["hits"] / total * 100, 1) if total else 0.0,
                "by_module": {m: sum(1 for e in self._store.values() if e.module == m)
                              for m in ["regression", "scenario", "financial"]},
            }

    def list_entries(self) -> List[dict]:
        with self._lock:
            return [{"key": e.key, "module": e.module,
                     "age_min": round((time.time() - e.created_at) / 60, 1),
                     "hits": e.hits, "expired": e.is_expired}
                    for e in self._store.values()]


class AnalysisHistoryManager:
    """Persistent JSON history of analysis runs (last 200)."""

    def __init__(self, history_file: Optional[str] = None):
        if history_file is None:
            base = Path(__file__).resolve().parent.parent / "outputs"
            base.mkdir(exist_ok=True)
            history_file = str(base / "analysis_history.json")
        self._file = Path(history_file)
        self._lock = threading.Lock()
        self._history: List[HistoryRecord] = []
        self._load()

    def _load(self):
        try:
            if self._file.exists():
                self._history = [HistoryRecord(**r)
                                 for r in json.loads(self._file.read_text("utf-8"))]
        except Exception:
            self._history = []

    def _save(self):
        try:
            self._file.write_text(
                json.dumps([asdict(r) for r in self._history[-200:]], indent=2, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass

    def record(self, module: str, input_summary: dict, result_summary: dict,
               duration: float, success: bool, error: str = "") -> str:
        import uuid
        rid = str(uuid.uuid4())[:8]
        rec = HistoryRecord(rid, module, datetime.now().isoformat(),
                            input_summary, result_summary,
                            round(duration, 3), success, error)
        with self._lock:
            self._history.append(rec)
            self._save()
        return rid

    def get_recent(self, module: Optional[str] = None, limit: int = 20) -> List[dict]:
        with self._lock:
            recs = list(reversed(self._history))
            if module:
                recs = [r for r in recs if r.module == module]
            return [asdict(r) for r in recs[:limit]]

    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._history)
            by_mod = {}
            for m in ["regression", "scenario", "financial"]:
                sub = [r for r in self._history if r.module == m]
                by_mod[m] = {
                    "count": len(sub),
                    "success_rate": round(sum(r.success for r in sub) / len(sub) * 100, 1) if sub else 0,
                    "avg_duration_s": round(sum(r.duration_seconds for r in sub) / len(sub), 2) if sub else 0,
                }
            return {"total_runs": total, "by_module": by_mod}

    def clear(self, module: Optional[str] = None):
        with self._lock:
            self._history = [r for r in self._history if module and r.module != module] if module else []
            self._save()


_cache = AnalysisCache(max_size=50)
_history = AnalysisHistoryManager()


def get_cache() -> AnalysisCache:
    return _cache


def get_history() -> AnalysisHistoryManager:
    return _history
