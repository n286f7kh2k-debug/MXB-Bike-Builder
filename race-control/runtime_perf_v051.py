from __future__ import annotations

import gc
import time


def tune_database(conn):
    """Safe SQLite runtime tuning for a desktop app with one primary connection.

    Keeps race/wallet data fully transactional; this only reduces filesystem churn and
    increases SQLite's in-process cache. Every pragma is optional/fail-closed.
    """
    pragmas = (
        'PRAGMA busy_timeout=3000',
        'PRAGMA temp_store=MEMORY',
        'PRAGMA cache_size=-65536',      # ~64 MiB page cache, bounded by SQLite
        'PRAGMA mmap_size=134217728',    # 128 MiB max mmap window when supported
        'PRAGMA synchronous=NORMAL',
    )
    for sql in pragmas:
        try:conn.execute(sql)
        except Exception:pass
    try:conn.execute('PRAGMA optimize')
    except Exception:pass
    return conn


class UiPerf:
    """Tiny UI debounce/measurement helper; no polling threads and no feature changes."""
    def __init__(self, root):
        self.root=root
        self._jobs={}
        self._last={}

    def debounce(self,key,delay_ms,fn):
        old=self._jobs.pop(key,None)
        if old is not None:
            try:self.root.after_cancel(old)
            except Exception:pass
        try:self._jobs[key]=self.root.after(int(delay_ms),lambda:self._run(key,fn))
        except Exception:fn()

    def _run(self,key,fn):
        self._jobs.pop(key,None)
        started=time.perf_counter()
        try:return fn()
        finally:self._last[key]=time.perf_counter()-started

    def cancel_all(self):
        for job in list(self._jobs.values()):
            try:self.root.after_cancel(job)
            except Exception:pass
        self._jobs.clear()

    def compact(self):
        # Occasional explicit collection after large page teardown; never in a hot loop.
        try:gc.collect(0)
        except Exception:pass
