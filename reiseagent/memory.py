import sqlite3
import numpy as np
import profile_store

_model = None

def _get_model():
    global _model
    if _model is None:
        print("[memory] Lade Embedding-Modell (einmalig ~5-10 Sekunden)...")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[memory] Embedding-Modell geladen.")
    return _model

def _embed(text):
    model = _get_model()
    vector = model.encode(text, convert_to_numpy=True)
    return vector.astype(np.float32)

def _cosine_similarity(a, b):
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)

def store_message(source, date, text):
    if not text or len(text.strip()) < 5:
        return
    profile_store.init_db()
    conn = sqlite3.connect(profile_store.DB_PATH)
    existing = conn.execute(
        "SELECT id FROM messages WHERE source=? AND date=? AND text=?",
        (source, date, text)
    ).fetchone()
    if existing:
        conn.close()
        return
    vector = _embed(text)
    blob = vector.tobytes()
    conn.execute(
        "INSERT OR IGNORE INTO messages (source, date, text, embedding) VALUES (?,?,?,?)",
        (source, date, text, blob)
    )
    conn.commit()
    conn.close()

    # Maximal 500 Eintraege behalten — aelteste loeschen
    conn = sqlite3.connect(profile_store.DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    if count > 500:
        conn.execute(
            "DELETE FROM messages WHERE id IN (SELECT id FROM messages ORDER BY saved_at ASC LIMIT ?)",
            (count - 500,)
        )
        conn.commit()
    conn.close()

def retrieve_context(query, k=4):
    profile_store.init_db()
    conn = sqlite3.connect(profile_store.DB_PATH)
    rows = conn.execute("SELECT text, embedding FROM messages WHERE embedding IS NOT NULL").fetchall()
    conn.close()

    if not rows:
        return []

    query_vec = _embed(query)
    scored = []
    for text, blob in rows:
        vec = np.frombuffer(blob, dtype=np.float32)
        score = _cosine_similarity(query_vec, vec)
        scored.append((score, text))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in scored[:k]]
