"""
Structured, PII-safe activity/error logging — one JSON-lines file per calendar day, so a log file
from an issue reported "even a week ago" is enough to reconstruct exactly what happened, without
ever containing PHI/PII. Researched approach (not novel): structured logging + redact-by-default +
daily rotation + bounded retention is the standard shape for "ship me a log file and I'll diagnose
it" support workflows.

Location: db.get_app_data_dir()/logs/YYYY-MM-DD.log — same app-data directory already used for the
database/case sessions/license file. The Electron shell writes its own startup/lifecycle events
into the SAME folder using the identical daily-file naming convention (see electron/applog.js) —
two components, not one literally-shared file (which would need real cross-process write-locking
for little benefit), but "zip the logs folder and send it" still produces everything in one place.

## What's safe to log vs. never logged (read this before adding a new log call)

ALWAYS SAFE: timestamps, HTTP method/path/status/duration, job/session/group IDs (already opaque
hex strings throughout this app), model name, token counts, chunk indices, license TIER (not the
customer/firm name string), exception type + full Python traceback (a standard traceback shows
source lines and function names, not local variable values, so it's safe by construction AS LONG AS
exception messages themselves never interpolate raw user content — see the next point).

NEVER LOGGED, EVER: uploaded/case filenames as-is (can contain patient names — log a count + total
size instead), extracted PDF text, prompts sent to the model, model completions/findings content,
patient demographics, plaintiff/defendant names, case folder paths (can embed a name in the path
itself). If you're about to log an exception's `str(e)` and that exception could have been raised
from code holding one of the above, log the exception TYPE and traceback instead of the message, or
rephrase the message at the raise site to describe the problem without echoing the actual content.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import db

LOGS_DIR = db.get_app_data_dir() / "logs"
RETENTION_DAYS = 90  # bounded disk growth; comfortably covers "even a week ago"

_lock = threading.Lock()  # guards file open/rollover — Flask's dev server is multi-threaded


class _DailyJsonlHandler(logging.Handler):
    """Recomputes today's date on every emit() rather than rotating on a timer — correct across
    midnight with no restart needed, and trivially correct after the process has been asleep/idle."""

    def __init__(self):
        super().__init__()
        self._current_date = None
        self._file = None

    def _ensure_file(self):
        # UTC, deliberately not local time — the Electron shell's own logger (electron/applog.js)
        # writes into the same folder using the same UTC-dated filename convention, so the two
        # components' logs for "the same day" actually land in the same file regardless of which
        # timezone the machine is in (local time would put them a day apart for part of the day in
        # any timezone behind UTC, e.g. anywhere in the Americas).
        today = datetime.now(timezone.utc).date().isoformat()
        if today != self._current_date:
            if self._file:
                self._file.close()
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            self._file = open(LOGS_DIR / f"{today}.log", "a", encoding="utf-8")
            self._current_date = today
        return self._file

    def emit(self, record: logging.LogRecord):
        try:
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "level": record.levelname,
                "component": "backend",
                "event": getattr(record, "event", record.funcName),
                "message": record.getMessage(),
            }
            context = getattr(record, "context", None)
            if context:
                entry["context"] = context
            if record.exc_info:
                entry["traceback"] = "".join(traceback.format_exception(*record.exc_info))
            line = json.dumps(entry, default=str)
        except Exception:
            return  # a logging bug must never crash the app it's trying to help diagnose

        with _lock:
            try:
                f = self._ensure_file()
                f.write(line + "\n")
                f.flush()
            except Exception:
                pass  # same reasoning — logging failures are swallowed, not raised


_logger = logging.getLogger("chronology_builder")
_logger.setLevel(logging.INFO)
_logger.addHandler(_DailyJsonlHandler())
_logger.propagate = False  # don't also duplicate into Flask's/root's own stderr handlers


def get_logger() -> logging.Logger:
    return _logger


def log_event(event: str, message: str, *, level: str = "INFO", context: dict | None = None,
              exc_info=None) -> None:
    """Convenience wrapper — `event` is a short machine-readable name (e.g. "case_started",
    "chunk_generation_failed"), `context` is a small dict of SAFE metadata only (see module
    docstring). Prefer this over calling get_logger() directly at most call sites."""
    _logger.log(
        getattr(logging, level, logging.INFO),
        message,
        extra={"event": event, "context": context},
        exc_info=exc_info,
    )


def cleanup_old_logs(retention_days: int = RETENTION_DAYS) -> None:
    """Deletes log files older than `retention_days` — call once at app startup. Best-effort: a
    failure here must never prevent the app from starting."""
    try:
        if not LOGS_DIR.is_dir():
            return
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=retention_days)
        for f in LOGS_DIR.glob("*.log"):
            try:
                file_date = datetime.strptime(f.stem, "%Y-%m-%d").date()
                if file_date < cutoff:
                    f.unlink()
            except ValueError:
                continue  # not a date-named log file — leave it alone
    except Exception:
        pass
