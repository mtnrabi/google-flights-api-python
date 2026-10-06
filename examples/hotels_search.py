"""Live Booking.com rates for a destination, with each property's coordinates."""
from flightpowers import FlightPowers

with FlightPowers() as fp:
    res = fp.search_hotels("Lisbon", "2026-11-17", "2026-11-20", adults=2, currency="USD")
    print(f"{len(res)} properties for {res.destination}, {res.checkin_date} to {res.checkout_date}")
    for h in res.properties[:3]:
        print(f"{h.price_string:>10}  {h.name}  score={h.review_score}  ({h.latitude}, {h.longitude})")
