"""Offline tests for the opt-in Nominatim-compatible geocoding adapter."""
import io
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from vlog_site.services import filming_geocoding


def test_normalize_geocoding_results_rejects_invalid_and_duplicate_coordinates():
    payload = [
        {"osm_type": "node", "osm_id": 10, "lat": "34.70", "lon": "-84.48",
         "display_name": "Ellijay, Georgia, USA"},
        {"osm_type": "node", "osm_id": 10, "lat": "34.70", "lon": "-84.48",
         "display_name": "Duplicate"},
        {"osm_type": "way", "osm_id": 11, "lat": "nan", "lon": "1", "display_name": "Invalid"},
        {"osm_type": "way", "osm_id": 12, "lat": "100", "lon": "1", "display_name": "Invalid"},
        {"osm_type": "way", "osm_id": 13, "lat": "34.71", "lon": "-84.49", "display_name": "Second place"},
    ]
    results = filming_geocoding.normalize_geocoding_results(payload)
    assert len(results) == 2
    assert results[0]["latitude"] == 34.7
    assert results[0]["osm_url"] == "https://www.openstreetmap.org/node/10"
    assert results[0]["source"] == "OpenStreetMap contributors"


def test_geocoder_rejects_unconfigured_and_unsafe_endpoints():
    with pytest.raises(filming_geocoding.GeocodingUnavailable):
        filming_geocoding.geocode_location("Ellijay GA", endpoint="", user_agent="VTF")
    with pytest.raises(filming_geocoding.GeocodingUnavailable):
        filming_geocoding.geocode_location("Ellijay GA", endpoint="http://example.com/search", user_agent="VTF")
    with pytest.raises(ValueError):
        filming_geocoding.geocode_location("x", endpoint="https://example.com/search", user_agent="VTF")


def test_geocoder_uses_bounded_request_and_attribution(monkeypatch):
    observed = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, size):
            return io.BytesIO(json.dumps([{
                "osm_type": "relation", "osm_id": 50, "lat": "34.7", "lon": "-84.48",
                "display_name": "Ellijay, Georgia"
            }]).encode()).read(size)
    def fake_open(request, timeout):
        observed.append((request, timeout))
        return Response()
    monkeypatch.setattr(filming_geocoding, "urlopen", fake_open)
    results = filming_geocoding.geocode_location(
        "Ellijay, GA", endpoint="https://geocode.example.test/search", user_agent="VTF-Test/1.0"
    )
    assert len(results) == 1
    parsed = urlsplit(observed[0][0].full_url)
    params = parse_qs(parsed.query)
    assert params["q"] == ["Ellijay, GA"]
    assert params["limit"] == ["5"]
    assert observed[0][1] == 8
    assert observed[0][0].get_header("User-agent") == "VTF-Test/1.0"


def test_geocoder_rejects_invalid_provider_payload(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, size): return b'{"unexpected":true}'
    monkeypatch.setattr(filming_geocoding, "urlopen", lambda *a, **k: Response())
    with pytest.raises(filming_geocoding.GeocodingUnavailable):
        filming_geocoding.geocode_location("Ellijay, GA", endpoint="https://example.test/search", user_agent="VTF")
