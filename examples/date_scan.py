"""Scan several departure dates and keep the cheapest fare on each.

One request per date. A PRO key allows 150 requests a minute, so a long scan
can run in a thread pool.
"""
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
