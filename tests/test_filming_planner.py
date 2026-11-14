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
