import uuid


def _item(label: str, category: str, priority: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "label": label,
        "category": category,
        "completed": False,
        "priority": priority,
    }


def create_checklist(trip_id: str, request: dict, weather: list) -> dict:
    items = [
        _item("Reisepass / Personalausweis", "documents", "high"),
        _item("Kreditkarte / Bargeld", "documents", "high"),
        _item("Reiseversicherung", "documents", "medium"),
        _item("Hotel-/Unterkunft-Buchung bestätigen", "booking", "high"),
        _item("Anreise buchen (Bahn/Flug)", "booking", "high"),
        _item("Handy-Ladekabel", "packing", "medium"),
        _item("Bequeme Schuhe", "packing", "medium"),
        _item("Kamera / Smartphone", "packing", "low"),
    ]

    rain_days = [w for w in weather if w.get("condition") in ("rain", "storm", "snow")]
    if rain_days:
        items.append(_item("Regenjacke / Regenschirm", "packing", "high"))
        items.append(_item("Wasserdichte Schuhe", "packing", "medium"))

    cold_weather = any(w.get("condition") == "snow" for w in weather)
    if cold_weather:
        items.append(_item("Warme Jacke / Winterkleidung", "packing", "high"))

    interests = [i.lower() for i in request.get("interests", [])]

    if any(kw in interests for kw in ["museen", "museum"]):
        items.append(_item("Museumspass / Tickets vorbuchen", "booking", "medium"))

    if any(kw in interests for kw in ["gutes essen", "restaurants", "fine dining"]):
        items.append(_item("Restaurant-Reservierungen", "booking", "medium"))

    if any(kw in interests for kw in ["spaziergaenge", "natur", "wandern"]):
        items.append(_item("Sportliche Kleidung / Wanderschuhe", "packing", "low"))

    travel_type = request.get("travel_type", "")
    if travel_type == "family":
        items.append(_item("Kinderausweis", "documents", "high"))
        items.append(_item("Erste-Hilfe-Set", "packing", "medium"))
    elif travel_type in ("couple", "solo"):
        items.append(_item("Stadtplan / Offline-Karte herunterladen", "preparation", "low"))

    items.append(_item("Notfallnummern speichern", "preparation", "medium"))
    items.append(_item("Lokale SIM-Karte / Roaming prüfen", "preparation", "low"))

    return {"trip_id": trip_id, "items": items}


def get_agent_insight() -> dict:
    return {
        "agent_name": "checklist_agent",
        "display_label": "Checklisten Agent",
        "status": "completed",
        "summary": "Packliste basierend auf Reisetyp und Wetter erstellt.",
    }
