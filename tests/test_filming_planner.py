"""Smoke coverage for the new filming planner workspace."""


def test_filming_planner_renders_for_visitor(client):
    response = client.get("/filming-planner")
    assert response.status_code == 200
    assert b"Filming Planner" in response.data
    assert b"Starting location" in response.data
    assert b"Print / Save PDF" in response.data
    assert b"Open selected route in Google Maps" in response.data
    assert b"not verified automatically" in response.data


def test_filming_planner_is_linked_from_navigation(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"/filming-planner" in response.data


def test_filming_schedule_controls_present(client):
    response = client.get("/filming-planner")
    assert response.status_code == 200
    assert b'id="travel"' in response.data
    assert b'id="schedule"' in response.data
    assert b'id="feasibility"' in response.data
    assert b"Estimated travel per leg" in response.data
    assert b"Film minutes" in response.data


def test_filming_catalog_discovery_returns_existing_places(client, seeded_content):
    response = client.get("/filming-planner/discover?location=Campground,%20Testville,%20TS")
    assert response.status_code == 200
    data = response.get_json()
    assert data["city"] == "Testville"
    assert data["source"] == "Vlog Travel Finder catalog"
    assert len(data["suggestions"]) == 1
    place = data["suggestions"][0]
    assert place["name"] == "Test Place"
    assert place["id"] == seeded_content["place"].id
    assert place["category"] == "Museums"
    assert place["place_url"].endswith("/places/" + str(place["id"]))
    assert "permissions" in place["why_film"]
    assert "unverified" in data["limitations"]


def test_filming_catalog_discovery_does_not_invent_locations(client, seeded_content):
    response = client.get("/filming-planner/discover?location=Elsewhere,%20ZZ")
    assert response.status_code == 200
    assert response.get_json()["suggestions"] == []


def test_filming_catalog_discovery_validates_location(client):
    assert client.get("/filming-planner/discover").status_code == 400
    assert client.get("/filming-planner/discover?location=" + "x" * 121).status_code == 400


def test_filming_catalog_discovery_respects_place_access_rule(client, db):
    from vlog_site.models import AccessRule
    rule = db.get(AccessRule, "places")
    if rule is None:
        db.add(AccessRule(feature="places", anonymous_access=False))
    else:
        rule.anonymous_access = False
    db.commit()
    response = client.get("/filming-planner/discover?location=Testville")
    assert response.status_code == 302
    assert "/register" in response.headers["Location"]


def test_filming_catalog_discovery_controls_render(client):
    response = client.get("/filming-planner")
    assert response.status_code == 200
    assert b'id="discoverStops"' in response.data
    assert b'id="discoverCity"' in response.data
    assert b'id="discoveryResults"' in response.data


def test_live_discovery_is_disabled_by_default(client):
    client.post("/register", data={"email": "osm-disabled@example.com", "password": "pw123456", "confirm": "pw123456"}, follow_redirects=True)
    response = client.get("/filming-planner/discover/nearby?latitude=34.75&longitude=-84.46")
    assert response.status_code == 503
    assert "disabled" in response.get_json()["error"]


def test_live_discovery_requires_account(client, app):
    app.config["FILMING_LIVE_DISCOVERY_ENABLED"] = True
    response = client.get("/filming-planner/discover/nearby?latitude=34.75&longitude=-84.46")
    assert response.status_code == 401


def test_live_discovery_uses_configured_provider_and_retains_provenance(client, app, monkeypatch):
    from vlog_site.blueprints import filming
    app.config.update(
        FILMING_LIVE_DISCOVERY_ENABLED=True,
        FILMING_OVERPASS_URL="https://osm.example.test/api/interpreter",
        FILMING_OSM_USER_AGENT="VlogTravelFinder-Test/1.0",
    )
    client.post("/register", data={"email": "osm-user@example.com", "password": "pw123456", "confirm": "pw123456"}, follow_redirects=True)
    observed = []
    def fake_discover(latitude, longitude, **kwargs):
        observed.append((latitude, longitude, kwargs))
        return [{"id": "node/19", "name": "Real Viewpoint", "category": "Scenic overlook",
                 "latitude": 34.75, "longitude": -84.46, "distance_km": 0.0,
                 "why_film": "Try an establishing shot.", "source": "OpenStreetMap contributors",
                 "osm_url": "https://www.openstreetmap.org/node/19",
                 "verification": "Hours and access unverified"}]
    monkeypatch.setattr(filming, "discover_osm_places", fake_discover)
    response = client.get("/filming-planner/discover/nearby?latitude=34.75&longitude=-84.46")
    assert response.status_code == 200
    assert response.get_json()["suggestions"][0]["id"] == "node/19"
    assert observed[0][2]["endpoint"] == "https://osm.example.test/api/interpreter"
    assert observed[0][2]["radius_m"] == 15000


def test_live_discovery_rejects_invalid_radius(client, app):
    app.config["FILMING_LIVE_DISCOVERY_ENABLED"] = True
    client.post("/register", data={"email": "osm-radius@example.com", "password": "pw123456", "confirm": "pw123456"}, follow_redirects=True)
    response = client.get("/filming-planner/discover/nearby?latitude=34.75&longitude=-84.46&radius_m=abc")
    assert response.status_code == 400


def test_live_discovery_controls_render(client):
    response = client.get("/filming-planner")
    assert response.status_code == 200
    assert b'id="discoverNearby"' in response.data
    assert b'id="nearLat"' in response.data
    assert b'id="nearLon"' in response.data
