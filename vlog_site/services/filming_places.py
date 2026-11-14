"""Opt-in, bounded OpenStreetMap Overpass POI discovery.

No network request is made unless an operator supplies a provider endpoint.
Public Overpass servers are rate-limited shared infrastructure, not an
unrestricted production backend. A single-process throttle is deliberately
NOT represented as a deployment-wide quota for multi-worker deployments.
"""
from __future__ import annotations

import json
import math
import threading
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


MAX_RESPONSE_BYTES = 1024 * 1024
CACHE_SECONDS = 15 * 60
MIN_QUERY_SPACING_SECONDS = 15
_CACHE: dict[tuple, tuple[float, list[dict]]] = {}
_LOCK = threading.Lock()
_LAST_QUERY_AT: float | None = None


class OSMDiscoveryUnavailable(RuntimeError):
    """Provider is disabled, rate limited, or unable to answer."""


def _validate_coordinates(latitude: float, longitude: float, radius_m: int) -> tuple[float, float, int]:
    try:
        lat, lon, radius = float(latitude), float(longitude), int(radius_m)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Coordinates and radius must be numeric") from exc
    if not math.isfinite(lat) or not -90 <= lat <= 90:
        raise ValueError("Latitude must be between -90 and 90")
    if not math.isfinite(lon) or not -180 <= lon <= 180:
        raise ValueError("Longitude must be between -180 and 180")
    if not 500 <= radius <= 30000:
        raise ValueError("Search radius must be between 500 and 30000 metres")
    return lat, lon, radius


def build_overpass_query(latitude: float, longitude: float, radius_m: int = 15000) -> str:
    """Produce a fixed-tag query; caller input never becomes Overpass syntax."""
    lat, lon, radius = _validate_coordinates(latitude, longitude, radius_m)
    area = f"(around:{radius},{lat:.6f},{lon:.6f})"
    return (
        "[out:json][timeout:10];("
        f'nwr{area}["tourism"~"^(viewpoint|museum|attraction)$"];'
        f'nwr{area}["natural"~"^(waterfall|peak)$"];'
        f'nwr{area}["waterway"="waterfall"];'
        f'nwr{area}["historic"];'
        f'nwr{area}["leisure"="park"];'
        f'nwr{area}["amenity"="marketplace"];'
        ");out center 80;"
    )


def _filming_category(tags: dict) -> tuple[str, str]:
    if tags.get("natural") == "waterfall" or tags.get("waterway") == "waterfall":
        return "Waterfall", "Consider scenic B-roll, an approach shot and a short introduction; verify trail and water conditions."
    if tags.get("tourism") == "viewpoint" or tags.get("natural") == "peak":
        return "Scenic overlook", "Consider establishing shots and a landscape reveal; verify walking access and weather."
    if tags.get("tourism") == "museum" or tags.get("historic"):
        return "Historic or cultural site", "Consider an exterior introduction and a local-history story; verify visitor hours and filming rules."
    if tags.get("amenity") == "marketplace":
        return "Local market", "Consider local food and vendor stories; confirm opening hours and obtain filming permission."
    if tags.get("leisure") == "park":
        return "Park", "Consider an outdoor walk-through with environmental B-roll; confirm accessibility and conditions."
    return "Attraction", "Consider arrival footage, distinctive exterior details and a location story; verify access."


def _distance_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    first, second = map(math.radians, (lat_a, lat_b))
    dlat = second - first
    dlon = math.radians(lon_b - lon_a)
    a = math.sin(dlat / 2) ** 2 + math.cos(first) * math.cos(second) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(a)))


def parse_overpass_places(payload: dict, latitude: float, longitude: float) -> list[dict]:
    """Validate, deduplicate and sort attributable OSM destinations."""
    lat, lon, _ = _validate_coordinates(latitude, longitude, 15000)
    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
        raise OSMDiscoveryUnavailable("Provider returned invalid destination data")
    found = []
    seen = set()
    for element in payload["elements"][:500]:
        if not isinstance(element, dict):
            continue
        kind, osm_id = element.get("type"), element.get("id")
        tags = element.get("tags")
        if kind not in {"node", "way", "relation"} or not isinstance(osm_id, int) or osm_id <= 0:
            continue
        if not isinstance(tags, dict) or not isinstance(tags.get("name"), str):
            continue
        name = tags["name"].strip()
        if not name or len(name) > 160 or tags.get("access") in {"no", "private"}:
            continue
        center = element.get("center")
        if not isinstance(center, dict):
            center = {}
        try:
            site_lat = float(element.get("lat", center.get("lat")))
            site_lon = float(element.get("lon", center.get("lon")))
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(site_lat) or not math.isfinite(site_lon):
            continue
        if not -90 <= site_lat <= 90 or not -180 <= site_lon <= 180:
            continue
        key = (kind, osm_id)
        if key in seen:
            continue
        seen.add(key)
        category, rationale = _filming_category(tags)
        found.append({
            "id": f"{kind}/{osm_id}",
            "name": name,
            "category": category,
            "latitude": site_lat,
            "longitude": site_lon,
            "distance_km": round(_distance_km(lat, lon, site_lat, site_lon), 1),
            "why_film": rationale,
            "source": "OpenStreetMap contributors",
            "osm_url": f"https://www.openstreetmap.org/{kind}/{osm_id}",
            "verification": "Hours, accessibility, permission and travel time are unverified",
        })
    found.sort(key=lambda p: (p["distance_km"], p["name"].casefold(), p["id"]))
    return found[:12]


def discover_osm_places(
    latitude: float,
    longitude: float,
    *,
    endpoint: str,
    user_agent: str,
    radius_m: int = 15000,
) -> list[dict]:
    """Fetch a bounded POI search from an operator-selected Overpass endpoint.

    Caches in one Python process. A public instance in a multi-worker deployment
    MUST additionally use shared caching and application-wide rate limiting.
    """
    global _LAST_QUERY_AT
    lat, lon, radius = _validate_coordinates(latitude, longitude, radius_m)
    target = urlsplit(endpoint or "")
    if target.scheme != "https" and not (
        target.scheme == "http" and target.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise OSMDiscoveryUnavailable("Configure an HTTPS provider or local Overpass instance")
    if not target.hostname or target.username or target.password or not user_agent.strip():
        raise OSMDiscoveryUnavailable("Provider URL and identifying User-Agent are required")
    key = (endpoint, round(lat, 5), round(lon, 5), radius)
    now = time.monotonic()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] < CACHE_SECONDS:
            return [dict(place) for place in cached[1]]
        if _LAST_QUERY_AT is not None and now - _LAST_QUERY_AT < MIN_QUERY_SPACING_SECONDS:
            raise OSMDiscoveryUnavailable("Provider request budget reached; retry shortly")
        _LAST_QUERY_AT = now
    query = build_overpass_query(lat, lon, radius)
    request = Request(
        endpoint,
        data=urlencode({"data": query}).encode("utf-8"),
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=12) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise OSMDiscoveryUnavailable("Provider response is too large")
        places = parse_overpass_places(json.loads(raw.decode("utf-8")), lat, lon)
    except (OSError, TimeoutError, ValueError, UnicodeError) as exc:
        raise OSMDiscoveryUnavailable("Destination provider is temporarily unavailable") from exc
    with _LOCK:
        _CACHE[key] = (time.monotonic(), [dict(place) for place in places])
    return places
