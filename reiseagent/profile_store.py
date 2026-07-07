import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "profile.db")

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS interests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            keyword TEXT NOT NULL,
            score REAL DEFAULT 1.0,
            source TEXT,
            seen_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS past_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            date TEXT,
            source TEXT,
            raw_text TEXT
        );
        CREATE TABLE IF NOT EXISTS free_days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            detected_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            activities TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            date TEXT,
            text TEXT NOT NULL,
            embedding BLOB,
            saved_at TEXT DEFAULT (datetime('now')),
            UNIQUE(source, date, text)
        );
        CREATE TABLE IF NOT EXISTS pending_prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            trip_id TEXT,
            created_at TEXT NOT NULL,
            resolved INTEGER DEFAULT 0,
            resolved_at TEXT,
            source TEXT DEFAULT 'telegram',
            metadata_json TEXT
        );
    """)
    conn.commit()
    conn.close()

def save_interest(category, keyword, score=1.0, source="unknown"):
    conn = _get_conn()
    existing = conn.execute("SELECT id, score FROM interests WHERE category=? AND keyword=?", (category, keyword)).fetchone()
    if existing:
        conn.execute("UPDATE interests SET score=?, seen_at=datetime('now') WHERE id=?", (existing["score"] + score, existing["id"]))
    else:
        conn.execute("INSERT INTO interests (category, keyword, score, source) VALUES (?,?,?,?)", (category, keyword, score, source))
    conn.commit()
    conn.close()

def save_past_event(name, category, date, source, raw_text=""):
    conn = _get_conn()
    conn.execute("INSERT OR IGNORE INTO past_events (name, category, date, source, raw_text) VALUES (?,?,?,?,?)", (name, category, date, source, raw_text))
    conn.commit()
    conn.close()

def save_free_day(date_str):
    conn = _get_conn()
    conn.execute("INSERT OR IGNORE INTO free_days (date) VALUES (?)", (date_str,))
    conn.commit()
    conn.close()

def replace_free_days(date_list):
    conn = _get_conn()
    conn.execute("DELETE FROM free_days")
    for date_str in date_list:
        conn.execute("INSERT OR IGNORE INTO free_days (date) VALUES (?)", (date_str,))
    conn.commit()
    conn.close()

def save_suggestion(date_str, title, description, activities):
    conn = _get_conn()
    conn.execute("INSERT INTO suggestions (date, title, description, activities) VALUES (?,?,?,?)", (date_str, title, description, json.dumps(activities, ensure_ascii=False)))
    conn.commit()
    conn.close()

def get_suggestion(suggestion_id):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM suggestions WHERE id=?", (suggestion_id,)).fetchone()
    conn.close()
    if not row:
        return None
    result = dict(row)
    result["activities"] = json.loads(result["activities"])
    return result

def get_suggestions_for_date(date_str):
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM suggestions WHERE date=? ORDER BY created_at ASC, id ASC", (date_str,)).fetchall()
    conn.close()
    results = []
    for row in rows:
        result = dict(row)
        result["activities"] = json.loads(result["activities"])
        results.append(result)
    return results

def get_top_interests(limit=10):
    conn = _get_conn()
    rows = conn.execute("SELECT category, keyword, SUM(score) as total FROM interests GROUP BY category, keyword ORDER BY total DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_past_events(limit=20):
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM past_events ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_upcoming_free_days(from_date=None, limit=10):
    from datetime import date
    if from_date is None:
        from_date = date.today().isoformat()
    conn = _get_conn()
    rows = conn.execute("SELECT date FROM free_days WHERE date >= ? ORDER BY date ASC LIMIT ?", (from_date, limit)).fetchall()
    conn.close()
    return [r["date"] for r in rows]

def get_pending_suggestions():
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM suggestions WHERE status='pending' ORDER BY date ASC").fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["activities"] = json.loads(d["activities"])
        results.append(d)
    return results

def update_suggestion_status(suggestion_id, status):
    conn = _get_conn()
    conn.execute("UPDATE suggestions SET status=? WHERE id=?", (status, suggestion_id))
    conn.commit()
    conn.close()

def update_pending_suggestions_status(status):
    conn = _get_conn()
    conn.execute("UPDATE suggestions SET status=? WHERE status='pending'", (status,))
    conn.commit()
    conn.close()


def create_pending_prompt(prompt_type, trip_id=None, metadata=None):
    """Legt eine neue offene Telegram-Frage an und gibt ihre id zurueck.

    MVP-Regel: es soll immer nur eine offene (unresolved) Frage gleichzeitig
    geben. Existiert bereits eine offene Frage, wird KEINE zweite erzeugt,
    sondern die id der bestehenden offenen Frage zurueckgegeben.
    """
    existing = get_open_pending_prompt()
    if existing:
        return existing["id"]

    metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
    created_at = datetime.now().isoformat(timespec="seconds")

    conn = _get_conn()
    cursor = conn.execute(
        "INSERT INTO pending_prompts (type, trip_id, created_at, metadata_json) VALUES (?,?,?,?)",
        (prompt_type, trip_id, created_at, metadata_json),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_open_pending_prompt(prompt_type=None):
    """Gibt die aelteste offene (unresolved) Frage zurueck, oder None.

    Wenn prompt_type gesetzt ist, wird nur nach diesem Typ gefiltert.
    """
    conn = _get_conn()
    if prompt_type:
        row = conn.execute(
            "SELECT * FROM pending_prompts WHERE resolved=0 AND type=? ORDER BY created_at ASC, id ASC LIMIT 1",
            (prompt_type,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM pending_prompts WHERE resolved=0 ORDER BY created_at ASC, id ASC LIMIT 1"
        ).fetchone()
    conn.close()

    if not row:
        return None

    result = dict(row)
    result["metadata"] = json.loads(result["metadata_json"]) if result.get("metadata_json") else None
    return result


def resolve_pending_prompt(prompt_id):
    """Markiert eine Frage als erledigt. Unbekannte ids werden ignoriert (kein Crash)."""
    conn = _get_conn()
    conn.execute(
        "UPDATE pending_prompts SET resolved=1, resolved_at=? WHERE id=?",
        (datetime.now().isoformat(timespec="seconds"), prompt_id),
    )
    conn.commit()
    conn.close()


def list_open_pending_prompts():
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM pending_prompts WHERE resolved=0 ORDER BY created_at ASC, id ASC"
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        d = dict(row)
        d["metadata"] = json.loads(d["metadata_json"]) if d.get("metadata_json") else None
        results.append(d)
    return results
