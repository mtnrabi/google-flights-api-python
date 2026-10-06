"""A small client for the FlightPowers REST API at https://api.flightpowers.com."""

from __future__ import annotations

import os
import time
from datetime import date
from typing import Any, Dict, Optional, Union

import httpx

from .models import HotelMatch, HotelSearch, Meta, OnewayFlight, Results, RoundtripItinerary

__version__ = "0.1.0"

BASE_URL = "https://api.flightpowers.com"
# Names this package in the API's own call logs. A label only: it changes no
# routing, billing or response.
CLIENT_ID = f"flightpowers-python/{__version__}"
RETRY_STATUSES = {429, 502, 503, 504}

DateLike = Union[str, date]


class FlightPowersError(Exception):
    """Any non-2xx answer. ``body`` is the parsed JSON (or text) the API sent."""

    def __init__(self, status_code: int, message: str, body: Any = None, meta: Optional[Meta] = None):
        super().__init__(f"{status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.body = body
        self.meta = meta


class AuthError(FlightPowersError):
    """401/403: no key, a wrong key, or a key not subscribed to that listing."""


class InvalidRequest(FlightPowersError):
    """400/422: the API refused a field. The message names it."""


class RateLimited(FlightPowersError):
    """429: over your plan's per-minute rate."""


class SearchIncomplete(FlightPowersError):
    """5xx: the search did not complete. Says nothing about availability."""

    @property
    def retry(self) -> bool:
        return not (isinstance(self.body, dict) and self.body.get("retry") is False)


def _iso(d: DateLike) -> str:
    return d.isoformat() if isinstance(d, date) else str(d)


def _message(body: Any) -> str:
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err.get("type") or err)
        for key in ("message", "detail", "help"):
            if body.get(key):
                return str(body[key])
        if err:
            return str(err)
    return str(body)[:500] if body else "no body"


def _meta(resp: httpx.Response) -> Meta:
    h = resp.headers
    remaining = h.get("x-plan-requests-remaining") or h.get("x-ratelimit-requests-remaining")
    return Meta(
        status_code=resp.status_code,
        search_status=h.get("x-search-status"),
        search_reason=h.get("x-search-reason"),
        search_notes=h.get("x-search-notes"),
        requests_remaining=int(remaining) if remaining and remaining.isdigit() else None,
        headers=dict(h),
    )


class FlightPowers:
    """Client for api.flightpowers.com.

    ``api_key`` is your RapidAPI key (default: the ``RAPIDAPI_KEY`` environment
    variable). Flights calls need a Google Flights Live API subscription, hotel
    calls a Booking Live API one; the same key works for both.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = BASE_URL,
        timeout: float = 120.0,
        max_retries: int = 2,
        backoff: float = 1.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        key = api_key or os.environ.get("RAPIDAPI_KEY")
        if not key:
            raise AuthError(401, "no API key: pass api_key= or set RAPIDAPI_KEY")
        self.max_retries = max_retries
        self.backoff = backoff
        self._http = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={
                "x-rapidapi-key": key,
                "x-fp-client": CLIENT_ID,
                "user-agent": CLIENT_ID,
                "content-type": "application/json",
            },
        )

    def __enter__(self) -> "FlightPowers":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    # -- flights --------------------------------------------------------

    def search_oneway(
        self, from_airport: str, to_airport: str, departure_date: DateLike, **params: Any
    ) -> Results[OnewayFlight]:
        """One-way fares. ``params``: max_stops, sort_type, airline_codes,
        currency, max_price, seat_type, passengers, limit, ... (see the docs)."""
        body = dict(params, from_airport=from_airport, to_airport=to_airport,
                    departure_date=_iso(departure_date))
        data, meta = self._post("/v1/flights/oneway", body)
        return Results([OnewayFlight.from_dict(r) for r in _rows(data)], meta)

    def search_roundtrip(
        self, from_airport: str, to_airport: str, departure_date: DateLike,
        return_date: DateLike, **params: Any
    ) -> Results[RoundtripItinerary]:
        """Round trips, both legs priced together as one itinerary."""
        body = dict(params, from_airport=from_airport, to_airport=to_airport,
                    departure_date=_iso(departure_date), return_date=_iso(return_date))
        data, meta = self._post("/v1/flights/roundtrip", body)
        return Results([RoundtripItinerary.from_dict(r) for r in _rows(data)], meta)

    # -- hotels ---------------------------------------------------------

    def search_hotels(
        self, destination: str, checkin_date: DateLike, checkout_date: DateLike, **params: Any
    ) -> HotelSearch:
        """Booking.com properties for a destination. ``params``: adults,
        children, currency, budget_per_night, filters, proxy_country."""
        body = dict(params, destination=destination, checkin_date=_iso(checkin_date),
                    checkout_date=_iso(checkout_date))
        data, meta = self._post("/v1/hotels/search", body)
        result = HotelSearch.from_dict(data if isinstance(data, dict) else {})
        result.meta = meta
        return result

    def find_hotel_by_name(
        self, hotel_name: str, checkin_date: DateLike, checkout_date: DateLike, **params: Any
    ) -> HotelMatch:
        """The rate for one named property. ``params``: area, adults, children,
        currency, proxy_country, free_cancellation."""
        body = dict(params, hotel_name=hotel_name, checkin_date=_iso(checkin_date),
                    checkout_date=_iso(checkout_date))
        data, meta = self._post("/v1/hotels/by-name", body)
        result = HotelMatch.from_dict(data if isinstance(data, dict) else {})
        result.meta = meta
        return result

    # -- transport ------------------------------------------------------

    def _post(self, path: str, body: Dict[str, Any]) -> "tuple[Any, Meta]":
        body = {k: v for k, v in body.items() if v is not None}
        attempt = 0
        while True:
            try:
                resp = self._http.post(path, json=body)
            except httpx.TransportError:
                if attempt >= self.max_retries:
                    raise
                self._sleep(attempt, None)
                attempt += 1
                continue
            meta = _meta(resp)
            try:
                data: Any = resp.json()
            except ValueError:
                data = resp.text
            if resp.is_success:
                return data, meta
            err = _error(resp.status_code, data, meta)
            retryable = resp.status_code in RETRY_STATUSES and not (
                isinstance(err, SearchIncomplete) and not err.retry)
            if not retryable or attempt >= self.max_retries:
                raise err
            self._sleep(attempt, resp.headers.get("retry-after"))
            attempt += 1

    def _sleep(self, attempt: int, retry_after: Optional[str]) -> None:
        delay = self.backoff * (2 ** attempt)
        if retry_after and retry_after.isdigit():
            delay = max(delay, min(float(retry_after), 30.0))
        time.sleep(delay)


def _rows(data: Any) -> list:
    # A bare array by default; an object with "results" when the request set
    # include_search_status=True.
    if isinstance(data, dict):
        return list(data.get("results") or [])
    return list(data or [])


def _error(status: int, body: Any, meta: Meta) -> FlightPowersError:
    cls = (
        AuthError if status in (401, 403)
        else InvalidRequest if status in (400, 422)
        else RateLimited if status == 429
        else SearchIncomplete if status >= 500
        else FlightPowersError
    )
    return cls(status, _message(body), body, meta)
