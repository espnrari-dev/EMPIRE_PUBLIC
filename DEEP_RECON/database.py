#!/usr/bin/env python3
import os
import sqlite3

HOME = os.path.expanduser("~")
DB_PATH = os.path.join(HOME, "deep_recon", "katana_seen.db")
EXPECTED_COLUMNS = ["market_key", "last_ts"]

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS seen (
    market_key TEXT PRIMARY KEY,
    last_ts REAL
);

CREATE TABLE IF NOT EXISTS runtime_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_ts REAL NOT NULL,
    component TEXT NOT NULL,
    event_type TEXT NOT NULL,
    market_key TEXT,
    detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_runtime_events_ts ON runtime_events(event_ts);
CREATE INDEX IF NOT EXISTS idx_runtime_events_component ON runtime_events(component);
"""

def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con

def initialize():
    con = connect()
    try:
        con.executescript(SCHEMA)
        columns = [row[1] for row in con.execute("PRAGMA table_info(seen)")]
        if columns != EXPECTED_COLUMNS:
            raise RuntimeError("INVALID ACTIVE SCHEMA: " + repr(columns))
    finally:
        con.close()

def verify():
    con = connect()
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError("SQLite integrity failure: " + str(integrity))
        columns = [row[1] for row in con.execute("PRAGMA table_info(seen)")]
        if columns != EXPECTED_COLUMNS:
            raise RuntimeError("INVALID seen schema: " + repr(columns))
        con.execute("SELECT last_ts FROM seen WHERE market_key=?", ("__internal_schema_test__",)).fetchone()
        return True
    finally:
        con.close()

def record_event(component, event_type, event_ts, market_key=None, detail=None):
    con = connect()
    try:
        con.execute(
            "INSERT INTO runtime_events (event_ts, component, event_type, market_key, detail) VALUES (?, ?, ?, ?, ?)",
            (float(event_ts), str(component), str(event_type), market_key, detail)
        )
    finally:
        con.close()
