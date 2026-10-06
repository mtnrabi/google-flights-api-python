"""Re-record the test fixtures by running an example against the live API.

    RAPIDAPI_KEY=... python tests/record_fixtures.py examples/oneway.py

Every exchange the example makes is saved as tests/fixtures/<example>-<n>.json:
the request path and JSON body, the response status, the X-Search-* headers and
the JSON body. The key travels in a header and is never written. Each request
is a real request on your RapidAPI plan.
"""

import json
import runpy
import sys
from pathlib import Path

import httpx

import flightpowers.client as client

OUT = Path(__file__).parent / "fixtures"
KEEP_HEADERS = ("content-type", "x-search-status", "x-search-reason", "x-search-notes")


class Recorder(httpx.BaseTransport):
    def __init__(self, name: str) -> None:
        self.inner = httpx.HTTPTransport()
        self.name = name
        self.count = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.inner.handle_request(request)
        response.read()
        self.count += 1
        record = {
            "request": {
                "method": request.method,
                "path": request.url.path,
                "json": json.loads(request.content or b"null"),
            },
            "response": {
                "status": response.status_code,
                "headers": {k: v for k, v in response.headers.items() if k.lower() in KEEP_HEADERS},
                "json": json.loads(response.content or b"null"),
            },
        }
        path = OUT / f"{self.name}-{self.count}.json"
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
        return response


def main(example: str) -> None:
    recorder = Recorder(Path(example).stem)
    original = client.FlightPowers.__init__

    def init(self, *args, **kwargs):
        kwargs.setdefault("transport", recorder)
        original(self, *args, **kwargs)

    client.FlightPowers.__init__ = init
    OUT.mkdir(exist_ok=True)
    runpy.run_path(example, run_name="__main__")


if __name__ == "__main__":
    main(sys.argv[1])
