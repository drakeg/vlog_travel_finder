"""Optional operator-configured geocoding adapter for Filming Planner.

This adapter is not enabled or called by default. A deployment must provide
a policy-compliant geocoder, application-wide request budgets, and user consent
before wiring it into public-facing routes.
"""
from __future__ import annotations

import json
import math
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

MAX_BYTES = 256 * 1024


class GeocodingUnavailable(RuntimeError):
    """Provider unavailable or response cannot be trusted."""


def normalize_geocoding_results(payload: object) -> list[dict]:
    """Return at most five distinct attributable, valid location candidates."""
    if not isinstance(payload, list):
        raise GeocodingUnavailable("Unexpected geocoder response")
    results = []
    seen = set()
    for item in payload[:25]:
        if not isinstance(item, dict):
            continue
        try:
            lat = float(item.get("lat"))
            lon = float(item.get("lon"))
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            continue
        name = item.get("display_name")
        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 500:
            continue
        osm_type, osm_id = item.get("osm_type"), item.get("osm_id")
        if osm_type not in {"node", "way", "relation"} or not isinstance(osm_id, int) or osm_id <= 0:
            continue
        key = (osm_type, osm_id)
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "name": name.strip(),
            "latitude": lat,
            "longitude": lon,
            "source": "OpenStreetMap contributors",
            "osm_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
        })
        if len(results) >= 5:
            break
    return results


def geocode_location(query: str, *, endpoint: str, user_agent: str) -> list[dict]:
    """Query an explicitly configured Nominatim-compatible service once.

    No caching/rate limits here: deployment-wide quotas must be enforced at a
    shared proxy before this adapter is connected to user-facing routes.
    """
    if not isinstance(query, str) or not 3 <= len(query.strip()) <= 160:
        raise ValueError("Location must contain 3–160 characters")
    if any(ord(char) < 32 for char in query):
        raise ValueError("Location contains invalid characters")
    parsed = urlsplit(endpoint or "")
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise GeocodingUnavailable("Configure a valid geocoder endpoint")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise GeocodingUnavailable("Geocoder requires HTTPS or a loopback service")
    if not user_agent or not user_agent.strip():
        raise GeocodingUnavailable("An identifying User-Agent is required")
    separator = "&" if "?" in endpoint else "?"
    url = endpoint + separator + urlencode({
        "q": query.strip(),
        "format": "jsonv2",
        "limit": "5",
        "addressdetails": "0",
    })
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=8) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise GeocodingUnavailable("Geocoder response too large")
        return normalize_geocoding_results(json.loads(raw.decode("utf-8")))
    except (OSError, TimeoutError, UnicodeError, ValueError) as exc:
        raise GeocodingUnavailable("Geocoder temporarily unavailable") from exc
