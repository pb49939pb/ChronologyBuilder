"""
Durable, long-term storage for LawFirmAgent's Case Mode data — SQLite via Python's stdlib
`sqlite3` module, deliberately: no new dependency, no server process to install/configure, no
account, no cost. This is what "free and comes bundled with the app without extra effort" means in
practice, and it works identically whether the Flask backend is running on this dev machine or the
real Windows tower (see TOWER_SETUP.md).

Everything here replaces the previous approach of storing each case as a JSON file under
`tempfile.gettempdir()` (see app.py's old BATCH_DIR) — that location is not guaranteed to survive
even a few days, let alone the "pull up a chronology from a month ago" requirement this module
exists to satisfy. A single SQLite file with foreign-key cascades also directly sets up the
retention/deletion policy PRODUCT_DEFINITION.md already flags as a future requirement: deleting a
case will eventually be one `DELETE FROM cases WHERE job_id=?` away, not a multi-location cleanup.
"""
from __future__ import annotations  # lets "X | None" annotations work on Python 3.9, not just 3.10+

import json
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path

DB_FILENAME = "lawfirmagent.db"

# Guards every write — SQLite connections are never shared across threads here (a fresh connection
# is opened and closed per call, see _connect), but concurrent writers from different threads
# (Flask's threaded=True request threads, plus the background case-processing thread) still need
# serializing at the application level; WAL mode alone allows concurrent readers during a writer,
# but not concurrent writers.
_write_lock = threading.Lock()


def get_app_data_dir() -> Path:
    """Per-OS persistent application-data directory — NOT tempfile.gettempdir(). An explicit
    LAWFIRMAGENT_DATA_DIR override takes precedence (same idiom as the existing LAWFIRMAGENT_PORT
    env var) — needed for test isolation, and because the real tower's Flask process might
    eventually run as a Windows Service under a service account, where %APPDATA% wouldn't resolve
    to the paralegal's own profile (see DESKTOP_PACKAGING.md/TOWER_SETUP.md)."""
    override = os.environ.get("LAWFIRMAGENT_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "LawFirmAgent"


def get_db_path() -> Path:
    return get_app_data_dir() / DB_FILENAME


def _connect() -> sqlite3.Connection:
    """Fresh connection per call, never shared across threads. WAL mode lets frequent manifest
    writes from the background processing thread not block a reviewer's concurrent GET requests."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db() -> None:
    """Creates tables/indices if they don't exist yet. Safe to call every time the app starts."""
    with _write_lock:
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    job_id TEXT PRIMARY KEY,
                    plaintiff_name TEXT,
                    folder TEXT,
                    status TEXT,
                    started_at REAL,
                    finished_at REAL,
                    manifest_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_cases_started_at ON cases(started_at DESC);

                CREATE TABLE IF NOT EXISTS processed_files (
                    job_id TEXT NOT NULL REFERENCES cases(job_id) ON DELETE CASCADE,
                    group_key TEXT NOT NULL,
                    rel_path TEXT NOT NULL,
                    processed_at REAL NOT NULL,
                    PRIMARY KEY (job_id, rel_path)
                );

                CREATE TABLE IF NOT EXISTS review_actions (
                    job_id TEXT NOT NULL REFERENCES cases(job_id) ON DELETE CASCADE,
                    group_key TEXT NOT NULL,
                    finding_id TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'finding',
                    status TEXT,
                    edited_text TEXT,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (job_id, group_key, finding_id)
                );

                CREATE TABLE IF NOT EXISTS added_facts (
                    job_id TEXT NOT NULL REFERENCES cases(job_id) ON DELETE CASCADE,
                    group_key TEXT NOT NULL,
                    fact_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (job_id, group_key, fact_id)
                );

                CREATE TABLE IF NOT EXISTS case_exports (
                    job_id TEXT NOT NULL REFERENCES cases(job_id) ON DELETE CASCADE,
                    group_key TEXT NOT NULL,
                    exported_at REAL NOT NULL,
                    PRIMARY KEY (job_id, group_key)
                );

                CREATE TABLE IF NOT EXISTS metadata_overrides (
                    job_id TEXT NOT NULL REFERENCES cases(job_id) ON DELETE CASCADE,
                    group_key TEXT NOT NULL,
                    field_key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (job_id, group_key, field_key)
                );
                """
            )
            conn.commit()

            # One-time schema fixup for dev/test DBs created before the folder-picker upload
            # redesign (see TEST_RESULTS.md): processed_files used to key on an absolute
            # filesystem path (abs_path); it's now a path relative to the case's own source_dir
            # (rel_path), since re-uploads never resolve to the same absolute path twice. This is a
            # prototype with no real case data to preserve (see the "no migration needed" note atop
            # this file) — renaming the column AND clearing its now-semantically-incompatible old
            # absolute-path values is the same clean-cutover approach already used when BATCH_DIR
            # was removed, not a real production migration.
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(processed_files)")}
            if "abs_path" in columns and "rel_path" not in columns:
                conn.execute("ALTER TABLE processed_files RENAME COLUMN abs_path TO rel_path")
                conn.execute("DELETE FROM processed_files")
                conn.commit()
        finally:
            conn.close()


# --- Case manifests ---------------------------------------------------------------------------

def save_case_manifest(job_id: str, manifest: dict) -> None:
    """Upsert. Drop-in replacement for the old write-a-JSON-file-to-temp-dir approach — same
    manifest dict shape as before, just persisted durably and atomically (a single SQLite
    UPDATE/INSERT can't leave a half-written file the way plain `path.write_text(json.dumps(...))`
    could on a crash mid-write, which the old code was actually exposed to given how often
    _run_case_job calls this)."""
    now = time.time()
    payload = (
        job_id,
        manifest.get("plaintiff_name"),
        manifest.get("folder_display_name"),
        manifest.get("status"),
        manifest.get("started_at"),
        manifest.get("finished_at"),
        json.dumps(manifest),
        now,
    )
    with _write_lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO cases (job_id, plaintiff_name, folder, status, started_at, finished_at, manifest_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    plaintiff_name=excluded.plaintiff_name, folder=excluded.folder, status=excluded.status,
                    started_at=excluded.started_at, finished_at=excluded.finished_at,
                    manifest_json=excluded.manifest_json, updated_at=excluded.updated_at
                """,
                payload,
            )
            conn.commit()
        finally:
            conn.close()


def load_case_manifest(job_id: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT manifest_json FROM cases WHERE job_id=?", (job_id,)).fetchone()
    finally:
        conn.close()
    return json.loads(row["manifest_json"]) if row else None


def list_case_manifests() -> list[dict]:
    """Every known case's manifest, most recently started first — replaces the old
    `sorted(BATCH_DIR.iterdir(), key=mtime)` + per-file json.load with a single query."""
    conn = _connect()
    try:
        rows = conn.execute("SELECT manifest_json FROM cases ORDER BY started_at DESC").fetchall()
    finally:
        conn.close()
    return [json.loads(r["manifest_json"]) for r in rows]


# --- Processed-file tracking, for incremental reprocessing -----------------------------------
# Keyed by path RELATIVE to the case's source_dir (get_app_data_dir()/case_sources/<job_id>/), not
# an absolute filesystem path — see the folder-picker rework in TEST_RESULTS.md: case files are now
# uploaded from the browser's own native folder picker rather than read directly off an arbitrary
# disk path, so a rescan's "what's new" identity has to be something a fresh browser upload can
# reproduce (its relative path within the picked folder), not a path Flask happened to resolve once.

def get_processed_paths(job_id: str) -> set[str]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT rel_path FROM processed_files WHERE job_id=?", (job_id,)).fetchall()
    finally:
        conn.close()
    return {r["rel_path"] for r in rows}


def record_processed_files(job_id: str, group_key: str, rel_paths: list[str]) -> None:
    now = time.time()
    with _write_lock:
        conn = _connect()
        try:
            conn.executemany(
                "INSERT OR REPLACE INTO processed_files (job_id, group_key, rel_path, processed_at) VALUES (?, ?, ?, ?)",
                [(job_id, group_key, p, now) for p in rel_paths],
            )
            conn.commit()
        finally:
            conn.close()


# --- Durable reviewer state (Case Mode only — job_id/group_key always present) ----------------

def save_review_action(job_id: str, group_key: str, finding_id: str, *, kind: str = "finding",
                        status: str | None = None, edited_text: str | None = None) -> None:
    """Upserts one row. Callers pass only the field(s) that changed; NULL for the others is fine —
    review_state is read back as a dict keyed by finding_id and each caller (approve/reject vs.
    edit) only cares about its own field, matching how the frontend's sessionStorage-based
    findingStatus/edits are already two independent dicts today."""
    now = time.time()
    with _write_lock:
        conn = _connect()
        try:
            existing = conn.execute(
                "SELECT status, edited_text FROM review_actions WHERE job_id=? AND group_key=? AND finding_id=?",
                (job_id, group_key, finding_id),
            ).fetchone()
            merged_status = status if status is not None else (existing["status"] if existing else None)
            merged_text = edited_text if edited_text is not None else (existing["edited_text"] if existing else None)
            conn.execute(
                """
                INSERT INTO review_actions (job_id, group_key, finding_id, kind, status, edited_text, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, group_key, finding_id) DO UPDATE SET
                    kind=excluded.kind, status=excluded.status, edited_text=excluded.edited_text, updated_at=excluded.updated_at
                """,
                (job_id, group_key, finding_id, kind, merged_status, merged_text, now),
            )
            conn.commit()
        finally:
            conn.close()


def load_review_state(job_id: str, group_key: str) -> dict:
    """Returns {finding_id: {"status": ..., "edited_text": ..., "kind": ...}} — the caller (a new
    /results response field) shapes this into whatever the frontend's sessionStorage pre-seed
    needs; kept generic here rather than baking in app.js's exact dict-of-dicts layout."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT finding_id, kind, status, edited_text FROM review_actions WHERE job_id=? AND group_key=?",
            (job_id, group_key),
        ).fetchall()
    finally:
        conn.close()
    return {
        r["finding_id"]: {"status": r["status"], "edited_text": r["edited_text"], "kind": r["kind"]}
        for r in rows
    }


def save_added_fact(job_id: str, group_key: str, fact_id: str, payload: dict) -> None:
    with _write_lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO added_facts (job_id, group_key, fact_id, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(job_id, group_key, fact_id) DO UPDATE SET payload_json=excluded.payload_json
                """,
                (job_id, group_key, fact_id, json.dumps(payload), time.time()),
            )
            conn.commit()
        finally:
            conn.close()


def delete_added_fact(job_id: str, group_key: str, fact_id: str) -> None:
    with _write_lock:
        conn = _connect()
        try:
            conn.execute(
                "DELETE FROM added_facts WHERE job_id=? AND group_key=? AND fact_id=?",
                (job_id, group_key, fact_id),
            )
            conn.commit()
        finally:
            conn.close()


def load_added_facts(job_id: str, group_key: str) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT payload_json FROM added_facts WHERE job_id=? AND group_key=? ORDER BY created_at",
            (job_id, group_key),
        ).fetchall()
    finally:
        conn.close()
    return [json.loads(r["payload_json"]) for r in rows]


# --- Review/export status (Case Mode only) -----------------------------------------------------
# "Reviewed" is deliberately NOT tracked here — it's derived at request time in app.py from
# count_decided() vs. each group's total finding count, so it can never drift out of sync with the
# review_actions/added_facts rows it's summarizing. "Exported" has no such derivable signal (an
# export is a one-off user action, not a running tally), so it gets its own small event table.

def mark_exported(job_id: str, group_key: str) -> None:
    with _write_lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO case_exports (job_id, group_key, exported_at)
                VALUES (?, ?, ?)
                ON CONFLICT(job_id, group_key) DO UPDATE SET exported_at=excluded.exported_at
                """,
                (job_id, group_key, time.time()),
            )
            conn.commit()
        finally:
            conn.close()


def get_exported_map(job_id: str) -> dict[str, float]:
    """{group_key: exported_at} for every exported group in this job — one query for the whole
    job rather than one per group, since callers (case_status/case_jobs_list) need this for every
    group in a manifest at once."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT group_key, exported_at FROM case_exports WHERE job_id=?",
            (job_id,),
        ).fetchall()
    finally:
        conn.close()
    return {r["group_key"]: r["exported_at"] for r in rows}


def count_decided(job_id: str) -> dict[str, int]:
    """{group_key: number of findings with a non-null review status} for every group in this job —
    the "decided" half of the derived reviewed/in-review/needs-review state, computed with one
    grouped query rather than once per group."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT group_key, COUNT(*) AS n FROM review_actions
            WHERE job_id=? AND kind='finding' AND status IS NOT NULL
            GROUP BY group_key
            """,
            (job_id,),
        ).fetchall()
    finally:
        conn.close()
    return {r["group_key"]: r["n"] for r in rows}


# --- Editable preview-modal overrides (Case Mode only) -----------------------------------------
# Case-level metadata a reviewer edits directly in the chronology preview (DOL, Facts, demographics,
# defendant names) — distinct from review_actions (per-finding approve/reject/edit) and added_facts
# (reviewer-added Key Facts). One row per edited field, upserted; unedited fields simply have no row
# and the caller falls back to the original AI-extracted/manually-entered value.

def save_metadata_override(job_id: str, group_key: str, field_key: str, value: str) -> None:
    with _write_lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO metadata_overrides (job_id, group_key, field_key, value, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(job_id, group_key, field_key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (job_id, group_key, field_key, value, time.time()),
            )
            conn.commit()
        finally:
            conn.close()


def load_metadata_overrides(job_id: str, group_key: str) -> dict[str, str]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT field_key, value FROM metadata_overrides WHERE job_id=? AND group_key=?",
            (job_id, group_key),
        ).fetchall()
    finally:
        conn.close()
    return {r["field_key"]: r["value"] for r in rows}


def delete_case(job_id: str) -> None:
    """Not wired to any route yet — exists so a future retention/deletion feature (see
    PRODUCT_DEFINITION.md) is one call away instead of a redesign. FK cascades remove
    processed_files/review_actions/added_facts automatically; the case's PDF directory
    (BATCH_SESSIONS_DIR/case_<job_id>_*) is the only other thing that would need removing."""
    with _write_lock:
        conn = _connect()
        try:
            conn.execute("DELETE FROM cases WHERE job_id=?", (job_id,))
            conn.commit()
        finally:
            conn.close()
