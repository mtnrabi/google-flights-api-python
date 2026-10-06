"""Typed rows for the four FlightPowers endpoints.

Every model keeps the full JSON object it was built from in ``raw``, so a field
the API adds later is never lost: read it from ``row.raw`` until this package
names it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Dict, Generic, Iterator, List, Optional, Type, TypeVar

T = TypeVar("T")
M = TypeVar("M", bound="_Model")


@dataclass
class _Model:
    raw: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls: Type[M], data: Dict[str, Any]) -> M:
        known = {f.name for f in fields(cls)} - {"raw", "meta"}
        return cls(raw=dict(data), **{k: v for k, v in data.items() if k in known})


@dataclass
class Meta:
    """What the response headers said about the call."""

    status_code: int
    search_status: Optional[str] = None  # X-Search-Status: ok, empty, partial, degraded
    search_reason: Optional[str] = None  # X-Search-Reason
    search_notes: Optional[str] = None  # X-Search-Notes
    requests_remaining: Optional[int] = None  # x-plan-requests-remaining
    headers: Dict[str, str] = field(default_factory=dict, repr=False)


@dataclass
class Stop(_Model):
    stop_airport: Optional[str] = None
    stop_duration_seconds: Optional[int] = None


@dataclass
class _PriceBand(_Model):
    # Google's own historical range for the route and dates, and its verdict
    # on this fare: "low", "typical" or "high". Null when Google shows none.
    price_insights_low: Optional[float] = None
    price_insights_high: Optional[float] = None
    price_range_in_relation_to_other_periods: Optional[str] = None


@dataclass
class OnewayFlight(_PriceBand):
    from_airport: Optional[str] = None
    to_airport: Optional[str] = None
    departure_date: Optional[str] = None
    price: Optional[str] = None
    price_as_number: Optional[float] = None
    airline: Optional[str] = None
    stops: Optional[int] = None
    stops_info: List[Stop] = field(default_factory=list)
    duration: Optional[str] = None
    duration_seconds: Optional[int] = None
    departure_description: Optional[str] = None
    arrival_description: Optional[str] = None
    buy_link: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OnewayFlight":
        row = super().from_dict(data)
        row.stops_info = [Stop.from_dict(s) for s in (data.get("stops_info") or [])]
        return row


@dataclass
class RoundtripItinerary(_PriceBand):
    from_airport: Optional[str] = None
    to_airport: Optional[str] = None
    departure_date: Optional[str] = None
    return_date: Optional[str] = None
    total_price: Optional[str] = None
    total_price_as_number: Optional[float] = None
    total_duration_seconds: Optional[int] = None
    total_stops: Optional[int] = None
    departure_flight_airline: Optional[str] = None
    departure_flight_stops: Optional[int] = None
    departure_flight_duration: Optional[str] = None
    departure_flight_departure_description: Optional[str] = None
    departure_flight_arrival_description: Optional[str] = None
    return_flight_airline: Optional[str] = None
    return_flight_stops: Optional[int] = None
    return_flight_duration: Optional[str] = None
    return_flight_departure_description: Optional[str] = None
    return_flight_arrival_description: Optional[str] = None
    departure_stops_info: List[Stop] = field(default_factory=list)
    return_stops_info: List[Stop] = field(default_factory=list)
    buy_link: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoundtripItinerary":
        row = super().from_dict(data)
        row.departure_stops_info = [Stop.from_dict(s) for s in (data.get("departure_stops_info") or [])]
        row.return_stops_info = [Stop.from_dict(s) for s in (data.get("return_stops_info") or [])]
        return row


@dataclass
class Hotel(_Model):
    """One property from ``/v1/hotels/search``. ``price`` is the whole stay."""

    name: Optional[str] = None
    price: Optional[float] = None
    price_string: Optional[str] = None
    review_score: Optional[float] = None
    review_count: Optional[int] = None
    room_type: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    nights: Optional[int] = None
    adults: Optional[int] = None
    children: Optional[int] = None
    image_url: Optional[str] = None
    link: Optional[str] = None
    retrieved_at: Optional[str] = None


@dataclass
class HotelSearch(_Model):
    destination: Optional[str] = None
    checkin_date: Optional[str] = None
    checkout_date: Optional[str] = None
    applied_filters: List[str] = field(default_factory=list)
    budget_per_night: Optional[float] = None
    retrieved_at: Optional[str] = None
    properties: List[Hotel] = field(default_factory=list)
    meta: Optional[Meta] = field(default=None, repr=False, compare=False)

    def __iter__(self) -> Iterator[Hotel]:
        return iter(self.properties)

    def __len__(self) -> int:
        return len(self.properties)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HotelSearch":
        res = super().from_dict(data)
        res.applied_filters = list(data.get("applied_filters") or [])
        res.properties = [Hotel.from_dict(p) for p in (data.get("properties") or [])]
        return res


@dataclass
class HotelMatch(_Model):
    """The property ``/v1/hotels/by-name`` matched, priced for the stay."""

    name: Optional[str] = None
    matched_name: Optional[str] = None
    matched_via: Optional[str] = None
    match_confidence: Optional[float] = None
    available: Optional[bool] = None
    price: Optional[float] = None
    price_string: Optional[str] = None
    review_score: Optional[float] = None
    review_count: Optional[int] = None
    room_type: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    nights: Optional[int] = None
    adults: Optional[int] = None
    children: Optional[int] = None
    image_url: Optional[str] = None
    link: Optional[str] = None
    retrieved_at: Optional[str] = None
    meta: Optional[Meta] = field(default=None, repr=False, compare=False)


@dataclass
class Results(Generic[T]):
    """A list of rows plus the call's ``meta``. Iterate it like a list."""

    items: List[T]
    meta: Meta

    def __iter__(self) -> Iterator[T]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int) -> T:
        return self.items[i]
