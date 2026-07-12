import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

import store
from agents.monitoring import monitor_trip


os.environ["MOCK_FLIGHT_DELAY_MINUTES"] = "45"

# Vorhandene Trips anzeigen, damit du die richtige ID findest.
trips = store.list_trips()

if not trips:
    raise RuntimeError(
        "Es wurde kein Trip gefunden. Erstelle zuerst über die Anwendung einen Trip."
    )

print("Gefundene Trips:")

for trip in trips:
    request = trip.get("request", {})
    print(
        f"- ID: {trip['id']} | "
        f"Ziel: {request.get('destination')} | "
        f"Flug: {request.get('flight_number')}"
    )

# Zum Testen zunächst den ersten gefundenen Trip verwenden.
trip_id = "add54099-9ac2-441a-aef1-44b2aefd2ce6"

print(f"\nTeste Trip: {trip_id}")

result = monitor_trip(
    trip_id,
    use_mock_weather=True,
    use_mock_flights=True,
)

print("\nMonitoring-Ergebnis:")
print(result)