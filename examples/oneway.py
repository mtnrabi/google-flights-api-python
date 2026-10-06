"""One-way fares JFK -> LHR on one date, with Google's own price verdict."""
from flightpowers import FlightPowers

with FlightPowers() as fp:  # reads RAPIDAPI_KEY
    flights = fp.search_oneway("JFK", "LHR", "2026-11-17", limit=3)
    print("search_status:", flights.meta.search_status)
    for f in flights:
        print(f"{f.price:>6}  stops={f.stops}  {f.departure_description:<24} {f.airline}")
    cheapest = min(flights, key=lambda f: f.price_as_number, default=None)
    if cheapest and cheapest.price_insights_low is not None:
        print(f"Google marks {cheapest.price} as {cheapest.price_range_in_relation_to_other_periods}"
              f" (usual range ${cheapest.price_insights_low:.0f} to ${cheapest.price_insights_high:.0f})")
