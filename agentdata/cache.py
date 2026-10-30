"""agentdata.cache — per-user local query cache (SQLite; TTL declared per op, api.md section 9.3).

Location ruling: defaults to the OS user cache directory
  Windows  %LOCALAPPDATA%\\agentdata\\cache.db (falls back to ~/AppData/Local without LOCALAPPDATA)
  POSIX    ~/.cache/agentdata/cache.db
env AGENTDATA_CACHE_DIR overrides; an unwritable directory falls back to the system temp dir;
if temp is unwritable too, an actionable error is raised (hinting --no-cache or
AGENTDATA_CACHE_DIR). The SDK cache is independent of any internal datastore.

TTL semantics: None=permanent (immutable keys: drug name -> RxCUI); a positive number=seconds
(mutable records: GUDID 7 days). Expired entries are evicted lazily (an expired read counts
as a miss).
"""
import json
import os
import pathlib
import sqlite3
import tempfile
import time
from datetime import datetime, timezone

DDL = """
CREATE TABLE IF NOT EXISTS thirdparty_cache (
  provider   TEXT NOT NULL,
  cache_key  TEXT NOT NULL,
  payload    TEXT NOT NULL,
  fetched_at INTEGER NOT NULL,   -- epoch ms
  ttl_sec    INTEGER,            -- NULL = permanent
  PRIMARY KEY (provider, cache_key)
)
"""


def default_cache_dir() -> pathlib.Path:
    env = os.environ.get("AGENTDATA_CACHE_DIR")
    if env:
        return pathlib.Path(env)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(pathlib.Path.home() / "AppData" / "Local")
        return pathlib.Path(base) / "agentdata"
    return pathlib.Path.home() / ".cache" / "agentdata"


def _open_or_none(dir_path: pathlib.Path):
    """Open cache.db under dir_path; return None on failure (the caller falls back to the next candidate)."""
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        p = dir_path / "cache.db"
        conn = sqlite3.connect(str(p), timeout=5)
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(DDL)
        conn.execute("INSERT OR REPLACE INTO thirdparty_cache (provider, cache_key, payload, fetched_at, ttl_sec) VALUES ('__probe','__probe','1',?,NULL)", (int(time.time() * 1000),))
        conn.commit()
        return conn
    except OSError:
        return None


class Cache:
    def __init__(self, cache_dir=None, enabled=True):
        self.enabled = enabled and True
        self._conn = None
        if not enabled:
            return
        cands = [pathlib.Path(cache_dir) if cache_dir else default_cache_dir(),
                 pathlib.Path(tempfile.gettempdir()) / "agentdata"]
        last_err = None
        for c in cands:
            self._conn = _open_or_none(c)
            if self._conn is not None:
                return
            last_err = c
        raise RuntimeError(
            f"Cache directory not writable (tried {cands}). Run with --no-cache, or point AGENTDATA_CACHE_DIR at a writable directory. (Last failed at {last_err})"
        )

    # —— hit -> {'payload': JSON as stored, 'fetched_at': epoch ms, 'fetched_at_iso': ISO8601Z}; miss/expired -> None ——
    def get(self, provider: str, cache_key: str, ttl_sec):
        if not self.enabled:
            return None
        row = self._conn.execute(
            "SELECT payload, fetched_at, ttl_sec FROM thirdparty_cache WHERE provider=? AND cache_key=?",
            (provider, cache_key),
        ).fetchone()
        if row is None:
            return None
        payload, fetched_at, row_ttl = row
        if row_ttl is not None and time.time() * 1000 - fetched_at >= row_ttl * 1000:
            return None
        return {
            "payload": json.loads(payload),
            "fetched_at": fetched_at,
            "fetched_at_iso": datetime.fromtimestamp(fetched_at / 1000, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        }

    def set(self, provider: str, cache_key: str, payload, ttl_sec):
        if not self.enabled:
            return
        self._conn.execute(
            "INSERT OR REPLACE INTO thirdparty_cache (provider, cache_key, payload, fetched_at, ttl_sec) VALUES (?,?,?,?,?)",
            (provider, cache_key, json.dumps(payload, ensure_ascii=False), int(time.time() * 1000), ttl_sec),
        )
        self._conn.commit()

    def delete(self, provider: str, cache_key: str):
        """Single-key delete: an occasional upstream "200 empty set" must not stand as cache authority
        (EUDAMED primaryDi un-indexed face); the provider drops the entry as soon as it sees emptiness."""
        if not self.enabled:
            return
        cur = self._conn.execute(
            "DELETE FROM thirdparty_cache WHERE provider=? AND cache_key=?", (provider, cache_key)
        )
        self._conn.commit()
        return cur.rowcount

