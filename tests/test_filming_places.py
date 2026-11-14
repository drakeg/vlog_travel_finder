"""Offline regression coverage for the opt-in Overpass destination adapter."""
import io
import json
from urllib.parse import parse_qs

import pytest

from vlog_site.services import filming_places


@pytest.fixture(autouse=True)
def reset_osm_cache(monkeypatch):
    filming_places._CACHE.clear()
    monkeypatch.setattr(filming_places, "_LAST_QUERY_AT", None)


def test_osm_query_is_fixed_bounded_and_uses_valid_coordinates():
    query = filming_places.build_overpass_query(34.75, -84.46, 12000)
    assert "(around:12000,34.750000,-84.460000)" in query
    assert "out center 80" in query
    with pytest.raises(ValueError):
        filming_places.build_overpass_query(float("nan"), 12)
    with pytest.raises(ValueError):
        filming_places.build_overpass_query(34.75, -84.46, 300000)


def test_osm_places_have_real_source_ids_categories_and_distance():
    source = {"elements": [
        {"type": "node", "id": 5, "lat": 34.75, "lon": -84.46, "tags": {"name": "Mountain View", "tourism": "viewpoint"}},
        {"type": "way", "id": 7, "center": {"lat": 34.76, "lon": -84.46}, "tags": {"name": "Falls", "natural": "waterfall"}},
        {"type": "node", "id": 5, "lat": 34.75, "lon": -84.46, "tags": {"name": "Duplicate"}},
        {"type": "node", "id": 8, "lat": 34.75, "lon": -84.46, "tags": {"name": "Private", "access": "private"}},
        {"type": "node", "id": 9, "lat": 34.75, "lon": -84.46, "tags": {"tourism": "museum"}},
    ]}
    places = filming_places.parse_overpass_places(source, 34.75, -84.46)
    assert [place["name"] for place in places] == ["Mountain View", "Falls"]
    assert places[0]["category"] == "Scenic overlook"
    assert places[0]["distance_km"] == 0.0
    assert places[0]["osm_url"] == "https://www.openstreetmap.org/node/5"
    assert "unverified" in places[0]["verification"]


def test_osm_discovery_requires_operator_configured_provider():
    with pytest.raises(filming_places.OSMDiscoveryUnavailable):
        filming_places.discover_osm_places(34.75, -84.46, endpoint="", user_agent="VlogTravelFinder")


def test_osm_discovery_fetches_once_then_caches(monkeypatch):
    requests = []
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self, length):
            return io.BytesIO(json.dumps({"elements": [
                {"type": "node", "id": 11, "lat": 34.75, "lon": -84.46, "tags": {"name": "Town Square", "historic": "yes"}}
            ]}).encode()).read(length)
    def fake_open(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()
    monkeypatch.setattr(filming_places, "urlopen", fake_open)
    options = {"endpoint": "https://osm.example.test/api/interpreter", "user_agent": "VlogTravelFinder/1.0"}
    first = filming_places.discover_osm_places(34.75, -84.46, **options)
    second = filming_places.discover_osm_places(34.75, -84.46, **options)
    assert first == second
    assert len(requests) == 1
    assert parse_qs(requests[0][0].data.decode())["data"][0].startswith("[out:json]")
    assert first[0]["source"] == "OpenStreetMap contributors"
    assert first[0]["id"] == "node/11"


def test_osm_rate_limit_rejects_distinct_uncached_search(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, length): return b'{"elements":[]}'
    monkeypatch.setattr(filming_places, "urlopen", lambda *a, **kw: Response())
    opts = {"endpoint": "https://osm.example.test", "user_agent": "VlogTravelFinder"}
    filming_places.discover_osm_places(34.75, -84.46, **opts)
    with pytest.raises(filming_places.OSMDiscoveryUnavailable, match="budget"):
        filming_places.discover_osm_places(34.76, -84.46, **opts)
