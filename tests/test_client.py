"""Replays responses recorded from the live API (tests/fixtures, made with
tests/record_fixtures.py on 2026-10-06). The few synthetic responses are
marked as such."""

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from flightpowers import (
    AuthError,
    FlightPowers,
    Hotel,
    InvalidRequest,
    OnewayFlight,
    RoundtripItinerary,
    SearchIncomplete,
    __version__,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def replay(*names, seen=None):
    """A transport that answers each request with the next recorded response,
    after checking it is the request that was recorded."""
    queue = [load(n) for n in names]

    def handler(request: httpx.Request) -> httpx.Response:
        rec = queue.pop(0)
        if seen is not None:
            seen.append(request)
        assert request.url.path == rec["request"]["path"]
        assert json.loads(request.content) == rec["request"]["json"]
        r = rec["response"]
        return httpx.Response(r["status"], headers=r["headers"], json=r["json"])

    return httpx.MockTransport(handler)


def client(transport, **kw):
    return FlightPowers("test-key", transport=transport, backoff=0, **kw)


def test_oneway_rows_band_and_headers():
    seen = []
    with client(replay("oneway-1", seen=seen)) as fp:
        flights = fp.search_oneway("JFK", "LHR", "2026-11-17", limit=3)
    assert len(flights) == 3 and all(isinstance(f, OnewayFlight) for f in flights)
    f = flights[0]
    assert f.price.startswith("$") and f.price_as_number > 0
    assert f.departure_date == "2026-11-17" and f.buy_link.startswith("https://www.google.com/travel/flights")
    assert f.price_range_in_relation_to_other_periods in ("low", "typical", "high")
    assert f.price_insights_low < f.price_insights_high
    assert flights.meta.search_status == "ok"
    req = seen[0]
    assert req.headers["x-rapidapi-key"] == "test-key"
    assert req.headers["x-fp-client"] == f"flightpowers-python/{__version__}"


def test_roundtrip_accepts_date_objects():
    with client(replay("roundtrip-1")) as fp:
        trips = fp.search_roundtrip("JFK", "LHR", date(2026, 11, 17), date(2026, 11, 24), limit=3)
    t = trips[0]
    assert isinstance(t, RoundtripItinerary)
    assert (t.departure_date, t.return_date) == ("2026-11-17", "2026-11-24")
    assert t.total_price_as_number > 0 and t.departure_flight_airline and t.return_flight_airline
    assert t.departure_stops_info == [] and t.total_stops == 0


def test_date_scan_three_requests():
    with client(replay("date_scan-1", "date_scan-2", "date_scan-3")) as fp:
        cheapest = [min(fp.search_oneway("JFK", "LHR", d), key=lambda r: r.price_as_number)
                    for d in ("2026-11-17", "2026-11-18", "2026-11-19")]
    assert [c.departure_date for c in cheapest] == ["2026-11-17", "2026-11-18", "2026-11-19"]


def test_hotels_search_has_coordinates():
    with client(replay("hotels_search-1")) as fp:
        res = fp.search_hotels("Lisbon", "2026-11-17", "2026-11-20", adults=2, currency="USD")
    assert res.destination == "Lisbon" and len(res) == len(res.properties) > 0
    h = res.properties[0]
    assert isinstance(h, Hotel) and h.name and h.price > 0
    assert 38 < h.latitude < 39 and -10 < h.longitude < -9  # Lisbon
    assert res.meta.status_code == 200


def test_find_hotel_by_name():
    with client(replay("hotel_by_name-1")) as fp:
        h = fp.find_hotel_by_name("The Hoxton Shoreditch", "2026-11-17", "2026-11-20",
                                  area="London", adults=2, currency="USD")
    assert h.available is True and h.nights == 3 and h.price > 0
    assert 51 < h.latitude < 52 and h.matched_name == "The Hoxton, Shoreditch"


def test_422_raises_invalid_request_without_retry():
    calls = []
    with client(replay("invalid_date-1", seen=calls)) as fp:
        with pytest.raises(InvalidRequest) as e:
            fp.search_oneway("JFK", "LHR", "2026-11-31")
    assert e.value.status_code == 422 and "departure_date" in e.value.message
    assert len(calls) == 1


# -- synthetic responses below -------------------------------------------------

def scripted(*responses):
    queue = list(responses)
    calls = []

    def handler(request):
        calls.append(request)
        return queue.pop(0)

    return httpx.MockTransport(handler), calls


def test_retries_a_503_marked_retry_then_succeeds():
    ok = load("oneway-1")["response"]
    t, calls = scripted(
        httpx.Response(503, json={"error": "search_incomplete", "search_reason": "blocked_page",
                                  "message": "did not complete", "retry": True}),
        httpx.Response(200, json=ok["json"], headers={"x-search-status": "ok"}),
    )
    with client(t) as fp:
        assert len(fp.search_oneway("JFK", "LHR", "2026-11-17")) == 3
    assert len(calls) == 2


def test_503_with_retry_false_is_not_retried():
    t, calls = scripted(httpx.Response(503, json={"error": "search_incomplete", "retry": False,
                                                  "message": "no render"}))
    with client(t) as fp, pytest.raises(SearchIncomplete) as e:
        fp.search_oneway("GRU", "NRT", "2026-11-13")
    assert e.value.retry is False and len(calls) == 1


def test_gives_up_after_max_retries():
    t, calls = scripted(*[httpx.Response(502, text="bad gateway") for _ in range(3)])
    with client(t, max_retries=2) as fp, pytest.raises(SearchIncomplete):
        fp.search_oneway("JFK", "LHR", "2026-11-17")
    assert len(calls) == 3


def test_401_is_auth_error():
    t, _ = scripted(httpx.Response(401, json={"error": {"type": "invalid_api_key", "message": "bad key"}}))
    with client(t) as fp, pytest.raises(AuthError) as e:
        fp.search_hotels("Rome", "2026-11-02", "2026-11-05")
    assert e.value.message == "bad key"


def test_missing_key(monkeypatch):
    monkeypatch.delenv("RAPIDAPI_KEY", raising=False)
    with pytest.raises(AuthError):
        FlightPowers()


def test_none_params_dropped_and_unknown_fields_kept():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"results": [{"price": "$1", "price_as_number": 1, "new_field": 7}]},
                              headers={"x-plan-requests-remaining": "42"})

    with client(httpx.MockTransport(handler)) as fp:
        rows = fp.search_oneway("JFK", "LHR", "2026-11-17", max_stops=None, include_search_status=True)
    assert "max_stops" not in seen[0]
    assert rows[0].raw["new_field"] == 7 and rows.meta.requests_remaining == 42
