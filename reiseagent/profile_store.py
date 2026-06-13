import sqlite3
import json
import os

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

def save_suggestion(date_str, title, description, activities):
    conn = _get_conn()
    conn.execute("INSERT INTO suggestions (date, title, description, activities) VALUES (?,?,?,?)", (date_str, title, description, json.dumps(activities, ensure_ascii=False)))
    conn.commit()
    conn.close()

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
