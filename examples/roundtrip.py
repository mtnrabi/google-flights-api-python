"""A round trip priced as one request: both legs, one total, one booking link."""
from flightpowers import FlightPowers

with FlightPowers() as fp:
    trips = fp.search_roundtrip("JFK", "LHR", "2026-11-17", "2026-11-24", limit=3)
    for t in trips:
        print(f"{t.total_price:>6}  out: {t.departure_flight_airline} ({t.departure_flight_stops} stops)"
              f"  back: {t.return_flight_airline} ({t.return_flight_stops} stops)")
    if trips:
        print("book:", trips[0].buy_link[:80] + "...")
