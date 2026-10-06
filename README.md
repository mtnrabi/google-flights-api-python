# Google Flights API for Python: live fares in one script

FlightPowers is a travel data API for developers and AI agents: live Google Flights fares with Google's own low / typical / high
price band and a round trip priced as one request, over REST, MCP servers and an n8n node on one RapidAPI key (also called a
flight price API, airfare API or flight search API). Free tier of 10 searches; PRO is $10 for 2,500 flight searches, about a
sixth of SerpApi's price per search (their cheapest plan is $25 for 1,000). Best for price tracking, date scans and AI agents;
it does not book.

This repo is the Python client for it: typed rows, retries, and the same key for the hotels endpoints. It is a client for a
hosted API, not a scraper, so there is no browser, proxy or HTML parser to maintain on your side.

```bash
pip install git+https://github.com/mtnrabi/google-flights-api-python
```

The package is `flightpowers` (`import flightpowers`). Python 3.9+, one dependency (`httpx`).

## Get a key

1. Subscribe to the [Google Flights Live API on RapidAPI](https://rapidapi.com/mtnrabi/api/google-flights-live-api).
   BASIC is free (10 searches a month), PRO is $10 for 2,500.
2. Copy your `x-rapidapi-key` and export it: `export RAPIDAPI_KEY=...`

For hotels, subscribe the same key to the [Booking Live API](https://rapidapi.com/mtnrabi/api/booking-live-api)
(free BASIC, PRO is $10 for 2,000).

## One-way fares, with Google's verdict on the price

```python
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
```

Output of a real run (2026-10-06 20:27 UTC; fares change by the minute):

```
search_status: ok
  $295  stops=0  8:00 AM on Tue, Nov 17   Virgin Atlantic | Air France, Delta, KLM
  $295  stops=0  9:30 AM on Tue, Nov 17   JetBlue
  $295  stops=0  6:25 PM on Tue, Nov 17   American | British Airways, Iberia, Finnair
Google marks $295 as typical (usual range $170 to $300)
```

`price_insights_low`, `price_insights_high` and `price_range_in_relation_to_other_periods` (`low` / `typical` / `high`) are
Google's own historical range for the route and dates. Leave `sort_type` out on one-way calls if you want them: a one-way
search sorted by price comes back without the band.

## A round trip in one request

Both legs are priced together: one total, one booking link, no second search with a token.

```python
from flightpowers import FlightPowers

with FlightPowers() as fp:
    trips = fp.search_roundtrip("JFK", "LHR", "2026-11-17", "2026-11-24", limit=3)
    for t in trips:
        print(f"{t.total_price:>6}  out: {t.departure_flight_airline} ({t.departure_flight_stops} stops)"
              f"  back: {t.return_flight_airline} ({t.return_flight_stops} stops)")
    if trips:
        print("book:", trips[0].buy_link[:80] + "...")
```

```
  $817  out: American | Iberia, Finnair, British Airways (0 stops)  back: British Airways | American, Finnair, Iberia (0 stops)
  $817  out: American | Iberia, Finnair, British Airways (0 stops)  back: British Airways | American, Finnair, Iberia (0 stops)
  $817  out: British Airways | American, Finnair, Iberia (0 stops)  back: British Airways | American, Finnair, Iberia (0 stops)
book: https://www.google.com/travel/flights?tfs=GjsSCjIwMjYtMTEtMTciHwoDSkZLEgoyMDI2LT...
```

## Scan dates

The REST API takes one date (or one date pair) per request, so a scan is a loop. PRO allows 150 requests a minute, so a
long scan can run in a thread pool.

```python
from flightpowers import FlightPowers

dates = ["2026-11-17", "2026-11-18", "2026-11-19"]
with FlightPowers() as fp:
    for d in dates:
        rows = fp.search_oneway("JFK", "LHR", d)
        f = min(rows, key=lambda r: r.price_as_number, default=None)
        if f:
            print(f"{d}  {f.price:>6}  Google says {f.price_range_in_relation_to_other_periods or 'n/a':<8} {f.airline}")
        else:
            print(f"{d}  no fare ({rows.meta.search_status})")
```

```
2026-11-17    $293  Google says typical  Aer Lingus
2026-11-18    $293  Google says typical  Aer Lingus
2026-11-19    $293  Google says typical  Aer Lingus
```

If you want a whole month and several destinations in one call from Claude, Cursor or another AI client, the
[MCP servers](https://github.com/mtnrabi/flights-mcp) take a date range and a list of airports and expand them for you.

## Hotels: live Booking.com rates, with coordinates

Live Booking.com room rates by destination or by hotel name, with a `proxy_country` parameter that prices the stay as seen
from another country. A hotel data API, not a booking engine.

```python
from flightpowers import FlightPowers

with FlightPowers() as fp:
    res = fp.search_hotels("Lisbon", "2026-11-17", "2026-11-20", adults=2, currency="USD")
    print(f"{len(res)} properties for {res.destination}, {res.checkin_date} to {res.checkout_date}")
    for h in res.properties[:3]:
        print(f"{h.price_string:>10}  {h.name}  score={h.review_score}  ({h.latitude}, {h.longitude})")
```

```
15 properties for Lisbon, 2026-11-17 to 2026-11-20
    US$455  Les Deux Mariettes Maison Rose  score=9.3  (38.7102142, -9.1501169)
    US$292  Madalena by The Beautique Hotels  score=8.8  (38.713205, -9.136545)
    US$331  TURIM Terreiro do Paço Hotel  score=8.7  (38.709253471491515, -9.135049495700855)
```

`price` is the whole stay. One named property:

```python
from flightpowers import FlightPowers

with FlightPowers() as fp:
    h = fp.find_hotel_by_name("The Hoxton Shoreditch", "2026-11-17", "2026-11-20",
                              area="London", adults=2, currency="USD")
    if h.available:
        print(f"{h.name}: {h.price_string} for {h.nights} nights, {h.room_type}")
        print(f"score {h.review_score} from {h.review_count} reviews, at ({h.latitude}, {h.longitude})")
    else:
        print("not available for those dates")
```

```
The Hoxton, Shoreditch: US$1,626 for 3 nights, Cozy Twin
score 8.7 from 352 reviews, at (51.525611900472484, -0.08284136652946472)
```

All five scripts are in [`examples/`](examples).

## What you get back

| Method | Returns | Row fields |
|---|---|---|
| `search_oneway(from_airport, to_airport, departure_date, **params)` | `Results[OnewayFlight]` | `price`, `price_as_number`, `airline`, `stops`, `stops_info`, `duration_seconds`, `departure_description`, `arrival_description`, `buy_link`, the three price-band fields |
| `search_roundtrip(from_airport, to_airport, departure_date, return_date, **params)` | `Results[RoundtripItinerary]` | `total_price`, `total_price_as_number`, `departure_flight_*`, `return_flight_*`, `total_stops`, `buy_link`, the price band |
| `search_hotels(destination, checkin_date, checkout_date, **params)` | `HotelSearch` (iterate it for `Hotel` rows) | `name`, `price`, `price_string`, `review_score`, `review_count`, `room_type`, `latitude`, `longitude`, `link`, `image_url` |
| `find_hotel_by_name(hotel_name, checkin_date, checkout_date, **params)` | `HotelMatch` | `available`, `matched_name`, `match_confidence`, `price`, `nights`, `latitude`, `longitude`, `link`, ... |

Dates take a `str` (`YYYY-MM-DD`) or a `datetime.date`. Every other request field goes in `**params` under its API name
(`max_stops`, `airline_codes`, `currency`, `seat_type`, `passengers`, `limit`, `use_fallback`, `budget_per_night`, `filters`,
`proxy_country`, ...); the API answers an unknown field with a 422 that names it rather than ignoring it. Field reference:
[flightpowers.com/docs](https://flightpowers.com/docs).

Every row keeps the full JSON object in `row.raw`, so a field the API adds later is readable before this package names it.
`results.meta` carries the call's `X-Search-Status` (`ok`, `empty`, `partial`, `degraded`), `X-Search-Reason` and the
requests left on your plan (`X-Plan-Requests-Remaining`) when the response carries it.

## Errors and retries

| Exception | When |
|---|---|
| `AuthError` | 401/403: no key, a wrong key, or a key not subscribed to that listing |
| `InvalidRequest` | 400/422: a field the API refused; `e.message` names it |
| `RateLimited` | 429: over your plan's per-minute rate |
| `SearchIncomplete` | 5xx: the search did not complete; this says nothing about availability |

All of them subclass `FlightPowersError` and carry `status_code`, `message` and the parsed `body`. 429, 502, 503 and 504 are
retried twice with backoff (1 s, 2 s, longer when the API sends `Retry-After`), except a 503 whose body says `"retry": false`.
`FlightPowers(max_retries=0)` turns retries off.

## The same call with curl

```bash
curl -X POST "https://api.flightpowers.com/v1/flights/oneway" \
  -H "x-api-key: $RAPIDAPI_KEY" \
  -H "Content-Type: application/json" \
  -d '{"from_airport":"JFK","to_airport":"LHR","departure_date":"2026-11-17"}'
```

The client sends `X-FP-Client: flightpowers-python/<version>` with each call so we can count calls from this package in our
own logs. It changes nothing about routing, billing or the response.

## Tests

```bash
pip install -e '.[test]'
pytest -q
```

The tests replay responses recorded from the live API on 2026-10-06 (`tests/fixtures`) and need no key.
`python tests/record_fixtures.py examples/oneway.py` re-records one example; each request it makes is a real request on your
plan.

## Links

- Flights API overview: [flightpowers.com/flights-api](https://flightpowers.com/flights-api)
- Docs and OpenAPI: [flightpowers.com/docs](https://flightpowers.com/docs)
- MCP servers for Claude, Cursor and Cline: [mtnrabi/flights-mcp](https://github.com/mtnrabi/flights-mcp) (source:
  [mtnrabi/google-flights-mcp](https://github.com/mtnrabi/google-flights-mcp))
- n8n node: [n8n-nodes-flightpowers](https://github.com/mtnrabi/n8n-nodes-flightpowers)

## Releasing to PyPI (maintainer, one-time setup)

Publishing runs from `.github/workflows/publish.yml` with PyPI trusted publishing, so no PyPI token is stored anywhere.

1. Sign in at [pypi.org](https://pypi.org) (create the account if needed) and turn on two-factor authentication.
2. Open [pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing/), go to "Add a new pending
   publisher", GitHub tab, and enter exactly: PyPI project name `flightpowers`, owner `mtnrabi`, repository name
   `google-flights-api-python`, workflow name `publish.yml`, environment name `pypi`. Click Add.
3. Push the tag: `git tag v0.1.0 && git push origin v0.1.0` (the `pypi` environment already exists on this repo).
4. Watch the `publish` run under Actions go green: it checks the tag matches `__version__`, runs the tests, builds and
   uploads.
5. Check [pypi.org/project/flightpowers](https://pypi.org/project/flightpowers/) shows 0.1.0 and `pip install flightpowers`
   works.

Later releases: bump `__version__` in `src/flightpowers/client.py`, commit, push a tag `v<version>`.

## License

MIT
