"""The live rate for one named hotel, for a given stay."""
from flightpowers import FlightPowers

with FlightPowers() as fp:
    h = fp.find_hotel_by_name("The Hoxton Shoreditch", "2026-11-17", "2026-11-20",
                              area="London", adults=2, currency="USD")
    if h.available:
        print(f"{h.name}: {h.price_string} for {h.nights} nights, {h.room_type}")
        print(f"score {h.review_score} from {h.review_count} reviews, at ({h.latitude}, {h.longitude})")
    else:
        print("not available for those dates")
