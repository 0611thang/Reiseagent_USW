import httpx
import os


def get_route(from_lat, from_lng, to_lat, to_lng, mode="foot-walking"):
    """
    Ruft eine Route von OpenRouteService ab.
    mode: "foot-walking", "driving-car", "cycling-regular"
    Gibt None zurück wenn kein API-Key oder Fehler.
    """
    api_key = os.getenv("ORS_API_KEY", "")
    if not api_key:
        return None

    url = f"https://api.openrouteservice.org/v2/directions/{mode}"
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    body = {"coordinates": [[from_lng, from_lat], [to_lng, to_lat]]}

    try:
        response = httpx.post(url, json=body, headers=headers, timeout=8.0)
        data = response.json()
        segment = data["routes"][0]["segments"][0]
        return {
            "duration_minutes": round(segment["duration"] / 60),
            "distance_km": round(segment["distance"] / 1000, 1),
            "mode": mode,
        }
    except Exception:
        return None
