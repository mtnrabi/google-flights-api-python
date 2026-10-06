"""FlightPowers: live Google Flights fares and Booking.com hotel rates over REST."""

from .client import (
    AuthError,
    FlightPowers,
    FlightPowersError,
    InvalidRequest,
    RateLimited,
    SearchIncomplete,
    __version__,
)
from .models import (
    Hotel,
    HotelMatch,
    HotelSearch,
    Meta,
    OnewayFlight,
    Results,
    RoundtripItinerary,
    Stop,
)

__all__ = [
    "FlightPowers",
    "FlightPowersError",
    "AuthError",
    "InvalidRequest",
    "RateLimited",
    "SearchIncomplete",
    "OnewayFlight",
    "RoundtripItinerary",
    "Stop",
    "Hotel",
    "HotelSearch",
    "HotelMatch",
    "Meta",
    "Results",
    "__version__",
]
