"""Minimal JSON HTTP client with optional forge authentication."""

from __future__ import annotations

import json
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HttpError(RuntimeError):
    pass


Transport = Callable[[Request], bytes]


def default_transport(request: Request) -> bytes:
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - URL is selected by integration code
            return response.read()
    except (HTTPError, URLError) as error:
        raise HttpError(str(error)) from error


class JsonClient:
    def __init__(self, transport: Transport = default_transport) -> None:
        self.transport = transport

    def get(self, url: str, headers: dict[str, str] | None = None) -> object:
        request = Request(url, headers={"Accept": "application/json", **(headers or {})})
        try:
            return json.loads(self.transport(request))
        except json.JSONDecodeError as error:
            raise HttpError(f"Invalid JSON from {url}") from error
