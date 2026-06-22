"""
Manueller Integrationstest fuer den Telegram Annehmen/Ablehnen-Button-Flow (Block A3).

Zweck: Pruefen, ob
  1. eine Proposal-Nachricht mit Inline-Buttons tatsaechlich in der Gruppe ankommt,
  2. ein Button-Klick als callback_query beim System ankommt,
  3. das System das Token korrekt aufloest und antworten kann.

Dieser Test isoliert die Telegram-Mechanik vom FastAPI-Backend (main.py).
Er pollt getUpdates selbst, daher: WAEHREND DES TESTS DARF `uvicorn main:app`
NICHT laufen, sonst entsteht ein getUpdates-409-Konflikt (genau der Bug, den
wir suchen). Laeuft das Backend parallel, meldet der Test das.

Start:
    cd reiseagent
    python test_telegram_buttons.py

Voraussetzungen in der .env (Projekt-Root):
    TELEGRAM_BOT_TOKEN=...
    TELEGRAM_CHAT_ID=...   (optional, sonst DEFAULT_CHAT_ID aus telegram.py)
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import store
from providers import telegram


POLL_TIMEOUT_SECONDS = 120  # so lange wartet der Test auf einen Klick


def _print_header(text: str) -> None:
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def _build_test_trip() -> dict:
    """Legt einen echten Trip in trips.db an (send_flight_delay_proposal
    schreibt die Callback-Tokens via store.update_trip zurueck)."""
    request = {
        "destination": "Teststadt",
        "duration_days": 2,
        "flight_number": "TEST123",
        "interests": ["Sehenswuerdigkeiten"],
    }
    trip = store.create_trip(request)
    return trip


def _build_test_proposal() -> dict:
    return {
        "id": "test-proposal-1",
        "trigger": "flight_delay",
        "status": "pending",
        "delay_minutes": 90,
        "budget_before": {"planned_total": 500},
        "budget_after": {"planned_total": 560},
    }


def _build_test_flight_updates() -> dict:
    return {
        "flight_number": "TEST123",
        "status": "delayed",
        "delay_minutes": 90,
    }


def _cleanup_trip(trip_id: str) -> None:
    conn = store._get_conn()
    conn.execute("DELETE FROM trips WHERE id=?", (trip_id,))
    conn.commit()
    conn.close()


def run() -> bool:
    _print_header("Telegram Button-Flow Test (A3)")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("FAIL: TELEGRAM_BOT_TOKEN ist nicht gesetzt (.env im Projekt-Root).")
        print("      Ohne Token sendet Telegram nichts und der Button kann nicht getestet werden.")
        return False
    print("OK: TELEGRAM_BOT_TOKEN gefunden.")
    print(f"OK: Ziel-Chat = {telegram._get_chat_id()}")

    store.init_db()

    # 1. Alte ausstehende Updates abraeumen, damit wir nur den frischen Klick sehen.
    drain = telegram.get_callback_updates()
    if not drain.get("ok", False):
        print("WARN: Erstes getUpdates lieferte ok=False. Moegliche Ursache:")
        print("      - laeuft 'uvicorn main:app' parallel? -> 409-Konflikt -> bitte beenden.")
    offset = None
    for upd in drain.get("result", []):
        offset = upd["update_id"] + 1

    trip = _build_test_trip()
    proposal = _build_test_proposal()
    flight_updates = _build_test_flight_updates()

    # 2. Nachricht mit Buttons senden.
    _print_header("Schritt 1/3: Nachricht mit Buttons senden")
    sent = telegram.send_flight_delay_proposal(trip, proposal, flight_updates)
    if not sent:
        print("FAIL: send_flight_delay_proposal hat False zurueckgegeben.")
        print("      Moegliche Ursachen: falsches Token, Bot nicht in der Gruppe,")
        print("      Chat-ID falsch, oder Callback-Tokens konnten nicht gespeichert werden.")
        _cleanup_trip(trip["id"])
        return False
    print("OK: Nachricht mit zwei Inline-Buttons gesendet.")

    # 3. Tokens aus dem Store laden (so wie es main.py spaeter tut).
    saved = store.get_trip(trip["id"])
    callbacks = saved.get("telegram_callbacks", {})
    if len(callbacks) != 2:
        print(f"FAIL: Erwartet 2 Callback-Tokens (accept/reject), gefunden: {len(callbacks)}.")
        _cleanup_trip(trip["id"])
        return False
    print(f"OK: {len(callbacks)} Callback-Tokens in trips.db gespeichert.")

    # 4. Auf den Klick warten.
    _print_header("Schritt 2/3: Bitte JETZT in Telegram einen Button klicken")
    print(f"Warte bis zu {POLL_TIMEOUT_SECONDS}s auf deinen Klick ...")

    deadline = time.time() + POLL_TIMEOUT_SECONDS
    clicked = None
    while time.time() < deadline:
        updates = telegram.get_callback_updates(offset=offset)
        if not updates.get("ok", False):
            print("WARN: getUpdates ok=False (laeuft das Backend parallel? 409-Konflikt).")
            time.sleep(3)
            continue
        for update in updates.get("result", []):
            offset = update["update_id"] + 1
            cq = update.get("callback_query")
            if cq:
                clicked = cq
                break
        if clicked:
            break
        time.sleep(2)

    if not clicked:
        print("FAIL: Innerhalb des Zeitfensters kam kein Button-Klick beim System an.")
        print("      Der Klick erreicht das System nicht -> hier liegt der Bug.")
        _cleanup_trip(trip["id"])
        return False

    # 5. Callback aufloesen (Logik wie in main.py:_telegram_callback_loop).
    _print_header("Schritt 3/3: Klick beim System angekommen - aufloesen")
    data = clicked.get("data", "")  # Format: "action:token"
    callback_id = clicked.get("id")
    print(f"OK: callback_query empfangen. data = '{data}'")

    if ":" not in data:
        print(f"FAIL: Unerwartetes callback_data-Format: '{data}'.")
        _cleanup_trip(trip["id"])
        return False

    action, click_token = data.split(":", 1)
    entry = callbacks.get(click_token)
    if not entry:
        print(f"FAIL: Token '{click_token}' nicht in gespeicherten Callbacks gefunden.")
        _cleanup_trip(trip["id"])
        return False
    if entry.get("action") != action:
        print(f"FAIL: Aktion stimmt nicht. Button='{action}', gespeichert='{entry.get('action')}'.")
        _cleanup_trip(trip["id"])
        return False

    print(f"OK: Token aufgeloest. Aktion = '{action}' (trip {entry.get('trip_id')}, proposal {entry.get('proposal_id')}).")

    # 6. Antwort an Telegram zurueck (das ist die Rueckmeldung ans System).
    answered = telegram.answer_callback_query(callback_id, f"Test erfolgreich: {action}")
    if answered:
        print("OK: answer_callback_query erfolgreich - Telegram hat die Antwort akzeptiert.")
    else:
        print("WARN: answer_callback_query gab False zurueck (Klick kam aber an).")

    _cleanup_trip(trip["id"])

    _print_header("ERGEBNIS: PASS")
    print("Der komplette Button-Flow funktioniert:")
    print("  Nachricht gesendet -> Klick empfangen -> Token aufgeloest -> geantwortet.")
    return True


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
