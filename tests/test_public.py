from vlog_site.db import get_session
from vlog_site.models import AccessRule
from vlog_site.models import PageView, Place, SavedPlace, Trip, TripPlace
from vlog_site.services.settings_service import set_setting

def test_home_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "--brand-1" in body
    assert "--brand-2" in body


def test_home_renders_latest_video_when_channel_configured(client, app, monkeypatch):
    rss = """<?xml version='1.0' encoding='UTF-8'?>
    <feed xmlns='http://www.w3.org/2005/Atom' xmlns:yt='http://www.youtube.com/xml/schemas/2015'>
      <entry>
        <yt:videoId>abc123</yt:videoId>
        <title>My Latest Upload</title>
      </entry>
    </feed>
    """

    with app.app_context():
        db = get_session(app)
        set_setting(db, "youtube_channel", "UC1234567890abcdef")
        db.commit()

    monkeypatch.setattr("vlog_site.services.youtube_service._CACHE", {})

    monkeypatch.setattr("vlog_site.services.youtube_service._fetch_rss", lambda channel_id: rss)

    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Latest video" in body
    assert "My Latest Upload" in body
    assert "https://www.youtube.com/watch?v=abc123" in body
    assert "https://www.youtube-nocookie.com/embed/abc123" in body
    assert "https://i.ytimg.com/vi/abc123/hqdefault.jpg" in body


def test_home_normalizes_featured_youtube_url_to_nocookie_embed(client, app):
    with app.app_context():
        db = get_session(app)
        set_setting(db, "featured_youtube_url", "https://www.youtube.com/watch?v=abc123")
        db.commit()

    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "data-embed-url=\"https://www.youtube-nocookie.com/embed/abc123\"" in body
    assert "https://i.ytimg.com/vi/abc123/hqdefault.jpg" in body
    assert "https://www.youtube.com/watch?v=abc123" in body


def test_home_latest_video_fallback_when_rss_blocked(client, app, monkeypatch):
    with app.app_context():
        db = get_session(app)
        set_setting(db, "youtube_channel", "UC1234567890abcdef")
        db.commit()

    def _boom(channel_id: str) -> str:
        raise RuntimeError("blocked")

    monkeypatch.setattr("vlog_site.services.youtube_service._CACHE", {})
    monkeypatch.setattr("vlog_site.services.youtube_service._fetch_rss", _boom)

    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Latest video unavailable" in body
    assert "https://www.youtube.com/channel/UC1234567890abcdef" in body


def test_page_view_logged_for_public_pages(client, app):
    resp = client.get("/", headers={"CF-IPCountry": "US"})
    assert resp.status_code == 200

    with app.app_context():
        db = get_session(app)
        rows = db.query(PageView).all()
        assert len(rows) >= 1
        assert rows[-1].path == "/"
        assert rows[-1].country == "US"


def test_page_view_not_logged_for_admin_or_static(client, app, admin_password):
    # Generate one public view first
    client.get("/")

    with app.app_context():
        db = get_session(app)
        baseline = db.query(PageView).count()

    # Admin page should not be logged
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": admin_password},
        follow_redirects=False,
    )
    resp = client.get("/admin/posts")
    assert resp.status_code == 200

    # Static asset should not be logged
    client.get("/static/style.css")

    with app.app_context():
        db = get_session(app)
        assert db.query(PageView).count() == baseline


def test_navbar_admin_and_preview_hidden_for_non_admin_user(client):
    resp = client.post(
        "/register",
        data={
            "email": "member@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert ">Admin<" not in body
    assert ">Preview<" not in body
    assert "Exit preview" not in body


def test_navbar_admin_hidden_during_anonymous_preview_but_exit_preview_visible_for_admin(client, admin_password):
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": admin_password},
        follow_redirects=True,
    )

    # Enable preview mode
    client.post("/admin/preview/anonymous", follow_redirects=True)

    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert ">Admin<" not in body
    assert "Exit preview" in body


def test_restricted_feature_redirects_to_register_with_encouraging_message(client, app):
    with app.app_context():
        db = get_session(app)
        rule = db.get(AccessRule, "places")
        if rule is None:
            db.add(AccessRule(feature="places", anonymous_access=False))
        else:
            rule.anonymous_access = False
        db.commit()

    resp = client.get("/places")
    assert resp.status_code == 302
    assert "/register" in resp.headers.get("Location", "")

    resp = client.get("/places", follow_redirects=True)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Create a free account" in body


def test_preview_mode_restricted_feature_matches_visitor_experience_and_allows_exit_preview(
    client, app, admin_password
):
    with app.app_context():
        db = get_session(app)
        rule = db.get(AccessRule, "places")
        if rule is None:
            db.add(AccessRule(feature="places", anonymous_access=False))
        else:
            rule.anonymous_access = False
        db.commit()

    client.post(
        "/login",
        data={"email": "admin@example.com", "password": admin_password},
        follow_redirects=True,
    )
    client.post("/admin/preview/anonymous", follow_redirects=True)

    resp = client.get("/places")
    assert resp.status_code == 302
    assert "/register" in resp.headers.get("Location", "")

    resp = client.get("/places", follow_redirects=True)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Create a free account" in body
    assert "Exit preview" in body
    assert ">Admin<" not in body


def test_places_ok(client):
    resp = client.get("/places")
    assert resp.status_code == 200


def test_about_ok(client):
    resp = client.get("/about")
    assert resp.status_code == 200


def test_blog_index_filters_scheduled_and_drafts(client, seeded_content):
    resp = client.get("/blog")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert "Published Past" in body
    assert "Published Future" not in body
    assert "Draft" not in body


def test_blog_post_404_for_future(client, seeded_content):
    resp = client.get("/blog/published-future")
    assert resp.status_code == 404


def test_contact_creates_message(client):
    resp = client.post(
        "/contact",
        data={
            "name": "Bob",
            "email": "bob@example.com",
            "subject": "Test",
            "message": "Hi",
            "website": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


def test_place_map_link_prefers_coordinates(client, app, seeded_content):
    with app.app_context():
        db = get_session(app)
        place = seeded_content["place"]
        place.latitude = 42.1234
        place.longitude = -76.5678
        place.address = "123 Main St"
        place.zipcode = "12345"
        db.commit()
        place_id = place.id

    resp = client.get(f"/places/{place_id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Open in Google Maps" in body
    assert "query=42.1234%2C-76.5678" in body


def test_place_map_link_falls_back_to_address(client, app, seeded_content):
    with app.app_context():
        db = get_session(app)
        place = seeded_content["place"]
        place.address = "123 Main St"
        place.city = "Testville"
        place.state = "TS"
        place.zipcode = "12345"
        place.latitude = None
        place.longitude = None
        db.commit()

    resp = client.get("/places")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Open in Google Maps" in body
    assert "query=123+Main+St%2C+Testville%2C+TS%2C+12345" in body


def test_places_filter_featured_in_vlog(client, app, seeded_content):
    with app.app_context():
        db = get_session(app)
        featured = Place(
            name="Featured Brewery",
            city="Testville",
            state="TS",
            vlog_youtube_url="https://www.youtube.com/watch?v=featured",
        )
        db.add(featured)
        db.commit()

    resp = client.get("/places?vlog_status=featured")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Featured Brewery" in body
    assert "Test Place" not in body
    assert 'option value="featured" selected' in body


def test_places_filter_not_featured_yet(client, app, seeded_content):
    with app.app_context():
        db = get_session(app)
        db.add(
            Place(
                name="Featured Brewery",
                city="Testville",
                state="TS",
                vlog_tiktok_url="https://www.tiktok.com/@example/video/1",
            )
        )
        db.commit()

    resp = client.get("/places?vlog_status=planned")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Test Place" in body
    assert "Featured Brewery" not in body
    assert 'option value="planned" selected' in body


def test_places_sort_by_name(client, app, seeded_content):
    with app.app_context():
        db = get_session(app)
        db.add(Place(name="Alpha Stop", city="Zedville", state="ZZ"))
        db.add(Place(name="Zulu Stop", city="Aardvark", state="AA"))
        db.commit()

    resp = client.get("/places?sort=name")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert body.index("Alpha Stop") < body.index("Test Place") < body.index("Zulu Stop")
    assert 'option value="name" selected' in body


def test_places_sort_by_newest(client, app, seeded_content):
    with app.app_context():
        db = get_session(app)
        db.add(Place(name="Newest Stop", city="Later", state="LS"))
        db.commit()

    resp = client.get("/places?sort=newest")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert body.index("Newest Stop") < body.index("Test Place")
    assert 'option value="newest" selected' in body


def test_places_invalid_sort_falls_back_to_location(client):
    resp = client.get("/places?sort=bogus")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'option value="location" selected' in body


def test_saved_places_require_login(client, seeded_content):
    place_id = seeded_content["place"].id
    resp = client.post(f"/places/{place_id}/save")
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")

    resp = client.get("/saved")
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")


def test_member_can_save_and_unsave_place_without_duplicates(client, app, seeded_content):
    place_id = seeded_content["place"].id
    client.post(
        "/register",
        data={
            "email": "member@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )

    for _ in range(2):
        resp = client.post(
            f"/places/{place_id}/save",
            data={"next": "/saved"},
            follow_redirects=True,
        )
        assert resp.status_code == 200

    with app.app_context():
        db = get_session(app)
        assert db.query(SavedPlace).filter_by(place_id=place_id).count() == 1

    resp = client.get("/saved")
    body = resp.get_data(as_text=True)
    assert "Test Place" in body

    resp = client.get("/places")
    assert "Saved" in resp.get_data(as_text=True)

    resp = client.post(
        f"/places/{place_id}/unsave",
        data={"next": "/saved"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Test Place" not in resp.get_data(as_text=True)

    with app.app_context():
        db = get_session(app)
        assert db.query(SavedPlace).filter_by(place_id=place_id).count() == 0


def test_saved_places_are_isolated_per_user(client, seeded_content):
    place_id = seeded_content["place"].id

    client.post(
        "/register",
        data={
            "email": "first@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post(f"/places/{place_id}/save")
    client.post("/logout")

    client.post(
        "/register",
        data={
            "email": "second@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    resp = client.get("/saved")
    assert resp.status_code == 200
    assert "Test Place" not in resp.get_data(as_text=True)


def test_saved_place_redirect_rejects_external_next(client, seeded_content):
    place_id = seeded_content["place"].id
    client.post(
        "/register",
        data={
            "email": "member@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )

    resp = client.post(
        f"/places/{place_id}/save",
        data={"next": "https://example.com/"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith(f"/places/{place_id}")


def test_trips_require_login(client, seeded_content):
    place_id = seeded_content["place"].id

    resp = client.get("/trips")
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")

    resp = client.post(f"/trips/1/places/{place_id}/add")
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")


def test_member_can_create_trip_and_add_place_once(client, app, seeded_content):
    place_id = seeded_content["place"].id
    client.post(
        "/register",
        data={
            "email": "tripmember@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )

    resp = client.post(
        "/trips",
        data={"name": "Finger Lakes Weekend"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Finger Lakes Weekend" in resp.get_data(as_text=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Finger Lakes Weekend").first()
        assert trip is not None
        trip_id = trip.id

    for _ in range(2):
        resp = client.post(
            f"/trips/{trip_id}/places/{place_id}/add",
            data={"next": f"/trips/{trip_id}"},
            follow_redirects=True,
        )
        assert resp.status_code == 200

    with app.app_context():
        db = get_session(app)
        assert db.query(TripPlace).filter_by(trip_id=trip_id, place_id=place_id).count() == 1

    body = client.get(f"/trips/{trip_id}").get_data(as_text=True)
    assert "Test Place" in body

    resp = client.post(
        f"/trips/{trip_id}/places/{place_id}/remove",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Test Place" not in resp.get_data(as_text=True)


def test_trip_ownership_is_enforced(client, app, seeded_content):
    place_id = seeded_content["place"].id

    client.post(
        "/register",
        data={
            "email": "owner@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Owner Trip"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Owner Trip").first()
        assert trip is not None
        trip_id = trip.id

    client.post("/logout")

    client.post(
        "/register",
        data={
            "email": "other@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )

    assert client.get(f"/trips/{trip_id}").status_code == 404
    assert client.post(f"/trips/{trip_id}/places/{place_id}/add").status_code == 404
    assert client.post(f"/trips/{trip_id}/delete").status_code == 404


def test_trip_delete_removes_trip_and_membership(client, app, seeded_content):
    place_id = seeded_content["place"].id
    client.post(
        "/register",
        data={
            "email": "delete@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Delete Me"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Delete Me").first()
        assert trip is not None
        trip_id = trip.id

    client.post(f"/trips/{trip_id}/places/{place_id}/add")
    resp = client.post(f"/trips/{trip_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert "Delete Me" not in resp.get_data(as_text=True)

    with app.app_context():
        db = get_session(app)
        assert db.get(Trip, trip_id) is None
        assert db.query(TripPlace).filter_by(trip_id=trip_id).count() == 0


def test_trip_notes_can_be_created_and_updated(client, app):
    client.post(
        "/register",
        data={
            "email": "notes@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )

    resp = client.post(
        "/trips",
        data={"name": "Notes Trip", "notes": "Initial notes"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Notes Trip").first()
        assert trip is not None
        assert trip.notes == "Initial notes"
        trip_id = trip.id

    resp = client.post(
        f"/trips/{trip_id}/update",
        data={"name": "Updated Notes Trip", "notes": "Campground at 3 PM"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Updated Notes Trip" in body
    assert "Campground at 3 PM" in body

    with app.app_context():
        db = get_session(app)
        trip = db.get(Trip, trip_id)
        assert trip is not None
        assert trip.name == "Updated Notes Trip"
        assert trip.notes == "Campground at 3 PM"


def test_trip_stops_append_and_can_be_reordered(client, app, seeded_content):
    first_place_id = seeded_content["place"].id

    with app.app_context():
        db = get_session(app)
        second = Place(name="Second Stop", city="Second City", state="SS")
        third = Place(name="Third Stop", city="Third City", state="TT")
        db.add_all([second, third])
        db.commit()
        second_id = second.id
        third_id = third.id

    client.post(
        "/register",
        data={
            "email": "ordering@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Ordered Trip"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Ordered Trip").first()
        assert trip is not None
        trip_id = trip.id

    for place_id in [first_place_id, second_id, third_id]:
        resp = client.post(
            f"/trips/{trip_id}/places/{place_id}/add",
            data={"next": f"/trips/{trip_id}"},
            follow_redirects=True,
        )
        assert resp.status_code == 200

    with app.app_context():
        db = get_session(app)
        rows = (
            db.query(TripPlace)
            .filter_by(trip_id=trip_id)
            .order_by(TripPlace.position.asc())
            .all()
        )
        assert [row.place_id for row in rows] == [first_place_id, second_id, third_id]
        assert [row.position for row in rows] == [1, 2, 3]

    # Moving the first item up is a safe no-op.
    resp = client.post(
        f"/trips/{trip_id}/places/{first_place_id}/move/up",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Move the third item up once: first, third, second.
    resp = client.post(
        f"/trips/{trip_id}/places/{third_id}/move/up",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert body.index("Test Place") < body.index("Third Stop") < body.index("Second Stop")

    with app.app_context():
        db = get_session(app)
        rows = (
            db.query(TripPlace)
            .filter_by(trip_id=trip_id)
            .order_by(TripPlace.position.asc())
            .all()
        )
        assert [row.place_id for row in rows] == [first_place_id, third_id, second_id]


def test_trip_update_and_move_enforce_ownership(client, app, seeded_content):
    place_id = seeded_content["place"].id

    client.post(
        "/register",
        data={
            "email": "trip-owner@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Private Ordered Trip"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Private Ordered Trip").first()
        assert trip is not None
        trip_id = trip.id

    client.post(f"/trips/{trip_id}/places/{place_id}/add")
    client.post("/logout")

    client.post(
        "/register",
        data={
            "email": "trip-intruder@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )

    assert (
        client.post(
            f"/trips/{trip_id}/update",
            data={"name": "Hijacked", "notes": "Nope"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/trips/{trip_id}/places/{place_id}/move/down"
        ).status_code
        == 404
    )


def test_trip_dates_persist_and_validate_range(client, app):
    client.post(
        "/register",
        data={
            "email": "dates@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )

    resp = client.post(
        "/trips",
        data={
            "name": "Dated Trip",
            "start_date": "2026-10-10",
            "end_date": "2026-10-15",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Dated Trip").first()
        assert trip is not None
        assert trip.start_date == "2026-10-10"
        assert trip.end_date == "2026-10-15"
        trip_id = trip.id

    resp = client.post(
        f"/trips/{trip_id}/update",
        data={
            "name": "Dated Trip",
            "start_date": "2026-10-20",
            "end_date": "2026-10-19",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Trip end date cannot be earlier than the start date" in resp.get_data(as_text=True)

    with app.app_context():
        db = get_session(app)
        trip = db.get(Trip, trip_id)
        assert trip is not None
        assert trip.start_date == "2026-10-10"
        assert trip.end_date == "2026-10-15"


def test_trip_rejects_invalid_iso_date(client, app):
    client.post(
        "/register",
        data={
            "email": "invalid-date@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )

    resp = client.post(
        "/trips",
        data={
            "name": "Invalid Date Trip",
            "start_date": "2026-02-30",
            "end_date": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Trip dates must use a valid YYYY-MM-DD date" in resp.get_data(as_text=True)

    with app.app_context():
        db = get_session(app)
        assert db.query(Trip).filter_by(name="Invalid Date Trip").first() is None


def test_stop_notes_persist_and_enforce_trip_ownership(client, app, seeded_content):
    place_id = seeded_content["place"].id

    client.post(
        "/register",
        data={
            "email": "stop-owner@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Stop Notes Trip"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Stop Notes Trip").first()
        assert trip is not None
        trip_id = trip.id

    client.post(f"/trips/{trip_id}/places/{place_id}/add")

    resp = client.post(
        f"/trips/{trip_id}/places/{place_id}/notes",
        data={"notes": "Arrive before 4 PM"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Arrive before 4 PM" in resp.get_data(as_text=True)

    with app.app_context():
        db = get_session(app)
        row = db.get(TripPlace, (trip_id, place_id))
        assert row is not None
        assert row.notes == "Arrive before 4 PM"

    client.post("/logout")
    client.post(
        "/register",
        data={
            "email": "stop-intruder@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )

    assert (
        client.post(
            f"/trips/{trip_id}/places/{place_id}/notes",
            data={"notes": "Hijacked"},
        ).status_code
        == 404
    )

    with app.app_context():
        db = get_session(app)
        row = db.get(TripPlace, (trip_id, place_id))
        assert row is not None
        assert row.notes == "Arrive before 4 PM"


def test_stop_schedule_persists_and_stays_within_trip_range(client, app, seeded_content):
    place_id = seeded_content["place"].id
    client.post(
        "/register",
        data={
            "email": "schedule@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post(
        "/trips",
        data={
            "name": "Scheduled Trip",
            "start_date": "2026-10-10",
            "end_date": "2026-10-15",
        },
        follow_redirects=True,
    )

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Scheduled Trip").first()
        assert trip is not None
        trip_id = trip.id

    client.post(f"/trips/{trip_id}/places/{place_id}/add")

    resp = client.post(
        f"/trips/{trip_id}/places/{place_id}/schedule",
        data={"planned_date": "2026-10-12", "planned_time": "14:30"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "2026-10-12" in body
    assert "14:30" in body

    with app.app_context():
        db = get_session(app)
        row = db.get(TripPlace, (trip_id, place_id))
        assert row is not None
        assert row.planned_date == "2026-10-12"
        assert row.planned_time == "14:30"

    resp = client.post(
        f"/trips/{trip_id}/places/{place_id}/schedule",
        data={"planned_date": "2026-10-20", "planned_time": "09:00"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Stop date must fall within the trip date range" in resp.get_data(as_text=True)

    with app.app_context():
        db = get_session(app)
        row = db.get(TripPlace, (trip_id, place_id))
        assert row is not None
        assert row.planned_date == "2026-10-12"
        assert row.planned_time == "14:30"


def test_stop_schedule_rejects_invalid_values_and_enforces_ownership(client, app, seeded_content):
    place_id = seeded_content["place"].id
    client.post(
        "/register",
        data={
            "email": "schedule-owner@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Private Schedule"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Private Schedule").first()
        assert trip is not None
        trip_id = trip.id

    client.post(f"/trips/{trip_id}/places/{place_id}/add")

    resp = client.post(
        f"/trips/{trip_id}/places/{place_id}/schedule",
        data={"planned_date": "2026-02-30", "planned_time": "25:00"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Stop schedule must use a valid date and time" in resp.get_data(as_text=True)

    client.post("/logout")
    client.post(
        "/register",
        data={
            "email": "schedule-intruder@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    assert (
        client.post(
            f"/trips/{trip_id}/places/{place_id}/schedule",
            data={"planned_date": "2026-10-12", "planned_time": "12:00"},
        ).status_code
        == 404
    )


def test_trip_itinerary_groups_stops_by_day_and_preserves_manual_order(client, app, seeded_content):
    first_place_id = seeded_content["place"].id

    with app.app_context():
        db = get_session(app)
        second = Place(name="Second Day Stop", city="City Two", state="NY")
        third = Place(name="Unscheduled Stop", city="City Three", state="PA")
        db.add_all([second, third])
        db.commit()
        second_id = second.id
        third_id = third.id

    client.post(
        "/register",
        data={
            "email": "dayview@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post(
        "/trips",
        data={
            "name": "Grouped Trip",
            "start_date": "2026-10-10",
            "end_date": "2026-10-15",
        },
        follow_redirects=True,
    )

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Grouped Trip").first()
        assert trip is not None
        trip_id = trip.id

    for place_id in [first_place_id, second_id, third_id]:
        client.post(f"/trips/{trip_id}/places/{place_id}/add")

    client.post(
        f"/trips/{trip_id}/places/{first_place_id}/schedule",
        data={"planned_date": "2026-10-12", "planned_time": "10:00"},
    )
    client.post(
        f"/trips/{trip_id}/places/{second_id}/schedule",
        data={"planned_date": "2026-10-11", "planned_time": "14:00"},
    )

    resp = client.get(f"/trips/{trip_id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    # Day sections are chronological, even though manual stop order is unchanged.
    assert body.index("2026-10-11") < body.index("2026-10-12") < body.index("Unscheduled")

    # Manual sequence numbers remain tied to the overall trip order.
    assert 'aria-label="Stop 1"' in body
    assert 'aria-label="Stop 2"' in body
    assert 'aria-label="Stop 3"' in body

    # All existing controls remain available after grouping.
    assert f"/trips/{trip_id}/places/{first_place_id}/move/up" in body
    assert f"/trips/{trip_id}/places/{first_place_id}/schedule" in body
    assert f"/trips/{trip_id}/places/{first_place_id}/notes" in body
    assert f"/trips/{trip_id}/places/{first_place_id}/remove" in body


def test_trip_itinerary_keeps_manual_order_within_same_day(client, app, seeded_content):
    first_place_id = seeded_content["place"].id

    with app.app_context():
        db = get_session(app)
        second = Place(name="Second Same Day Stop")
        db.add(second)
        db.commit()
        second_id = second.id

    client.post(
        "/register",
        data={
            "email": "same-day@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Same Day Trip"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Same Day Trip").first()
        assert trip is not None
        trip_id = trip.id

    client.post(f"/trips/{trip_id}/places/{first_place_id}/add")
    client.post(f"/trips/{trip_id}/places/{second_id}/add")
    for place_id in [first_place_id, second_id]:
        client.post(
            f"/trips/{trip_id}/places/{place_id}/schedule",
            data={"planned_date": "2026-10-12", "planned_time": ""},
        )

    body = client.get(f"/trips/{trip_id}").get_data(as_text=True)
    assert body.index("Test Place") < body.index("Second Same Day Stop")


def test_empty_trip_shows_itinerary_empty_state(client, app):
    client.post(
        "/register",
        data={
            "email": "empty-itinerary@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Empty Trip"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Empty Trip").first()
        assert trip is not None
        trip_id = trip.id

    resp = client.get(f"/trips/{trip_id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "No itinerary stops yet" in body
    assert "Add places to this trip to start building the itinerary." in body


def test_itinerary_exports_require_login(client):
    assert client.get("/trips/1/print").status_code == 302
    assert client.get("/trips/1/itinerary.txt").status_code == 302


def test_itinerary_exports_include_trip_and_stop_details(client, app, seeded_content):
    place_id = seeded_content["place"].id
    client.post(
        "/register",
        data={
            "email": "export@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post(
        "/trips",
        data={
            "name": "Export Trip",
            "start_date": "2026-10-10",
            "end_date": "2026-10-12",
            "notes": "Trip-level notes",
        },
        follow_redirects=True,
    )

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Export Trip").first()
        assert trip is not None
        trip_id = trip.id

    client.post(f"/trips/{trip_id}/places/{place_id}/add")
    client.post(
        f"/trips/{trip_id}/places/{place_id}/schedule",
        data={"planned_date": "2026-10-11", "planned_time": "13:30"},
    )
    client.post(
        f"/trips/{trip_id}/places/{place_id}/notes",
        data={"notes": "Stop-level notes"},
    )

    print_resp = client.get(f"/trips/{trip_id}/print")
    assert print_resp.status_code == 200
    print_body = print_resp.get_data(as_text=True)
    assert "Export Trip" in print_body
    assert "2026-10-10" in print_body
    assert "2026-10-12" in print_body
    assert "Trip-level notes" in print_body
    assert "2026-10-11" in print_body
    assert "13:30" in print_body
    assert "Stop-level notes" in print_body
    assert "Test Place" in print_body
    assert f"/trips/{trip_id}/update" not in print_body
    assert f"/trips/{trip_id}/places/{place_id}/schedule" not in print_body
    assert f"/trips/{trip_id}/places/{place_id}/notes" not in print_body
    assert f"/trips/{trip_id}/places/{place_id}/remove" not in print_body

    text_resp = client.get(f"/trips/{trip_id}/itinerary.txt")
    assert text_resp.status_code == 200
    assert text_resp.mimetype == "text/plain"
    assert (
        text_resp.headers["Content-Disposition"]
        == f'attachment; filename="trip-{trip_id}-itinerary.txt"'
    )
    text_body = text_resp.get_data(as_text=True)
    assert "Export Trip" in text_body
    assert "Dates: 2026-10-10 - 2026-10-12" in text_body
    assert "Trip notes: Trip-level notes" in text_body
    assert "2026-10-11" in text_body
    assert "1. Test Place @ 13:30" in text_body
    assert "Notes: Stop-level notes" in text_body
    assert "Maps:" in text_body


def test_itinerary_exports_enforce_trip_ownership(client, app):
    client.post(
        "/register",
        data={
            "email": "export-owner@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Private Export"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Private Export").first()
        assert trip is not None
        trip_id = trip.id

    client.post("/logout")
    client.post(
        "/register",
        data={
            "email": "export-intruder@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )

    assert client.get(f"/trips/{trip_id}/print").status_code == 404
    assert client.get(f"/trips/{trip_id}/itinerary.txt").status_code == 404


def test_empty_trip_exports_have_clear_content(client, app):
    client.post(
        "/register",
        data={
            "email": "empty-export@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Empty Export"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Empty Export").first()
        assert trip is not None
        trip_id = trip.id

    assert "No itinerary stops yet." in client.get(
        f"/trips/{trip_id}/print"
    ).get_data(as_text=True)
    assert "No itinerary stops yet." in client.get(
        f"/trips/{trip_id}/itinerary.txt"
    ).get_data(as_text=True)


def test_calendar_export_requires_login(client):
    assert client.get("/trips/1/itinerary.ics").status_code == 302


def test_calendar_export_contains_all_day_and_timed_events(client, app, seeded_content):
    first_place_id = seeded_content["place"].id

    with app.app_context():
        db = get_session(app)
        second = Place(
            name="Brewery, Taproom; East",
            address="123 Main St",
            city="Ithaca",
            state="NY",
            zipcode="14850",
        )
        third = Place(name="Unscheduled Calendar Stop")
        db.add_all([second, third])
        db.commit()
        second_id = second.id
        third_id = third.id

    client.post(
        "/register",
        data={
            "email": "calendar@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Calendar Trip"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Calendar Trip").first()
        assert trip is not None
        trip_id = trip.id

    for place_id in [first_place_id, second_id, third_id]:
        client.post(f"/trips/{trip_id}/places/{place_id}/add")

    client.post(
        f"/trips/{trip_id}/places/{first_place_id}/schedule",
        data={"planned_date": "2026-10-11", "planned_time": ""},
    )
    client.post(
        f"/trips/{trip_id}/places/{second_id}/schedule",
        data={"planned_date": "2026-10-12", "planned_time": "13:30"},
    )
    client.post(
        f"/trips/{trip_id}/places/{second_id}/notes",
        data={"notes": "Bring ID; ask for patio, then film"},
    )

    resp = client.get(f"/trips/{trip_id}/itinerary.ics")
    assert resp.status_code == 200
    assert resp.mimetype == "text/calendar"
    assert (
        resp.headers["Content-Disposition"]
        == f'attachment; filename="trip-{trip_id}-itinerary.ics"'
    )

    body = resp.get_data(as_text=True)
    assert "BEGIN:VCALENDAR\r\n" in body
    assert "VERSION:2.0\r\n" in body
    assert body.count("BEGIN:VEVENT") == 2
    assert "DTSTART;VALUE=DATE:20261011" in body
    assert "DTSTART:20261012T133000" in body
    assert "SUMMARY:Brewery\\, Taproom\\; East" in body
    assert "LOCATION:123 Main St\\, Ithaca\\, NY\\, 14850" in body
    assert "Bring ID\\; ask for patio\\, then film" in body
    assert "Maps:" in body
    assert "Unscheduled Calendar Stop" not in body


def test_calendar_export_enforces_ownership(client, app):
    client.post(
        "/register",
        data={
            "email": "calendar-owner@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Private Calendar"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Private Calendar").first()
        assert trip is not None
        trip_id = trip.id

    client.post("/logout")
    client.post(
        "/register",
        data={
            "email": "calendar-intruder@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    assert client.get(f"/trips/{trip_id}/itinerary.ics").status_code == 404


def test_calendar_export_without_scheduled_stops_is_valid(client, app):
    client.post(
        "/register",
        data={
            "email": "calendar-empty@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "No Events"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="No Events").first()
        assert trip is not None
        trip_id = trip.id

    body = client.get(f"/trips/{trip_id}/itinerary.ics").get_data(as_text=True)
    assert body.startswith("BEGIN:VCALENDAR\r\n")
    assert body.endswith("END:VCALENDAR\r\n")
    assert "BEGIN:VEVENT" not in body


def test_trip_duplicate_copies_metadata_and_stops_independently(client, app, seeded_content):
    place_id = seeded_content["place"].id
    client.post(
        "/register",
        data={
            "email": "duplicate@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post(
        "/trips",
        data={
            "name": "Original Trip",
            "notes": "Original notes",
            "start_date": "2026-10-10",
            "end_date": "2026-10-12",
        },
        follow_redirects=True,
    )

    with app.app_context():
        db = get_session(app)
        original = db.query(Trip).filter_by(name="Original Trip").first()
        assert original is not None
        original_id = original.id

    client.post(f"/trips/{original_id}/places/{place_id}/add")
    client.post(
        f"/trips/{original_id}/places/{place_id}/schedule",
        data={"planned_date": "2026-10-11", "planned_time": "09:30"},
    )
    client.post(
        f"/trips/{original_id}/places/{place_id}/notes",
        data={"notes": "Original stop notes"},
    )

    resp = client.post(f"/trips/{original_id}/duplicate", follow_redirects=False)
    assert resp.status_code == 302

    with app.app_context():
        db = get_session(app)
        duplicate = db.query(Trip).filter_by(name="Original Trip (Copy)").first()
        assert duplicate is not None
        duplicate_id = duplicate.id
        assert duplicate_id != original_id
        assert duplicate.notes == "Original notes"
        assert duplicate.start_date == "2026-10-10"
        assert duplicate.end_date == "2026-10-12"

        original_stop = db.get(TripPlace, (original_id, place_id))
        duplicate_stop = db.get(TripPlace, (duplicate_id, place_id))
        assert original_stop is not None
        assert duplicate_stop is not None
        assert duplicate_stop.position == original_stop.position
        assert duplicate_stop.notes == "Original stop notes"
        assert duplicate_stop.planned_date == "2026-10-11"
        assert duplicate_stop.planned_time == "09:30"

    client.post(
        f"/trips/{duplicate_id}/update",
        data={
            "name": "Changed Copy",
            "notes": "Changed notes",
            "start_date": "2026-10-10",
            "end_date": "2026-10-12",
        },
    )
    client.post(
        f"/trips/{duplicate_id}/places/{place_id}/notes",
        data={"notes": "Changed stop notes"},
    )

    with app.app_context():
        db = get_session(app)
        original = db.get(Trip, original_id)
        original_stop = db.get(TripPlace, (original_id, place_id))
        assert original is not None
        assert original.name == "Original Trip"
        assert original.notes == "Original notes"
        assert original_stop is not None
        assert original_stop.notes == "Original stop notes"


def test_trip_duplicate_enforces_ownership(client, app):
    client.post(
        "/register",
        data={
            "email": "duplicate-owner@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Private Source"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Private Source").first()
        assert trip is not None
        trip_id = trip.id

    client.post("/logout")
    client.post(
        "/register",
        data={
            "email": "duplicate-intruder@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    assert client.post(f"/trips/{trip_id}/duplicate").status_code == 404


def test_trip_duplicate_handles_empty_trip(client, app):
    client.post(
        "/register",
        data={
            "email": "duplicate-empty@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Empty Source"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Empty Source").first()
        assert trip is not None
        trip_id = trip.id

    resp = client.post(f"/trips/{trip_id}/duplicate", follow_redirects=True)
    assert resp.status_code == 200
    assert "Empty Source (Copy)" in resp.get_data(as_text=True)

    with app.app_context():
        db = get_session(app)
        duplicate = db.query(Trip).filter_by(name="Empty Source (Copy)").first()
        assert duplicate is not None
        assert (
            db.query(TripPlace).filter_by(trip_id=duplicate.id).count()
            == 0
        )


def test_saved_place_can_be_added_to_owned_trip(client, app, seeded_content):
    place_id = seeded_content["place"].id
    client.post(
        "/register",
        data={
            "email": "saved-single@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post(f"/places/{place_id}/save")
    client.post("/trips", data={"name": "Saved Single Trip"}, follow_redirects=True)

    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Saved Single Trip").first()
        assert trip is not None
        trip_id = trip.id

    resp = client.post(
        "/saved/add-to-trip",
        data={"trip_id": str(trip_id), "place_ids": str(place_id)},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Added 1 saved place to Saved Single Trip" in resp.get_data(as_text=True)

    with app.app_context():
        db = get_session(app)
        row = db.get(TripPlace, (trip_id, place_id))
        assert row is not None
        assert row.position == 1


def test_saved_places_bulk_add_appends_and_skips_duplicates(client, app, seeded_content):
    first_id = seeded_content["place"].id
    with app.app_context():
        db = get_session(app)
        second = Place(name="Bulk Second")
        third = Place(name="Bulk Third")
        db.add_all([second, third])
        db.commit()
        second_id = second.id
        third_id = third.id

    client.post(
        "/register",
        data={
            "email": "saved-bulk@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    for place_id in [first_id, second_id, third_id]:
        client.post(f"/places/{place_id}/save")

    client.post("/trips", data={"name": "Bulk Trip"}, follow_redirects=True)
    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Bulk Trip").first()
        assert trip is not None
        trip_id = trip.id

    client.post(f"/trips/{trip_id}/places/{first_id}/add")

    resp = client.post(
        "/saved/add-to-trip",
        data={
            "trip_id": str(trip_id),
            "place_ids": [str(first_id), str(second_id), str(third_id)],
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Added 2 saved places to Bulk Trip" in resp.get_data(as_text=True)

    with app.app_context():
        db = get_session(app)
        rows = (
            db.query(TripPlace)
            .filter_by(trip_id=trip_id)
            .order_by(TripPlace.position.asc())
            .all()
        )
        assert [row.place_id for row in rows] == [first_id, second_id, third_id]
        assert [row.position for row in rows] == [1, 2, 3]


def test_saved_places_bulk_add_rejects_other_users_trip(client, app, seeded_content):
    place_id = seeded_content["place"].id

    client.post(
        "/register",
        data={
            "email": "saved-owner@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post("/trips", data={"name": "Owner Trip"}, follow_redirects=True)
    with app.app_context():
        db = get_session(app)
        trip = db.query(Trip).filter_by(name="Owner Trip").first()
        assert trip is not None
        trip_id = trip.id

    client.post("/logout")
    client.post(
        "/register",
        data={
            "email": "saved-other@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post(f"/places/{place_id}/save")

    assert (
        client.post(
            "/saved/add-to-trip",
            data={"trip_id": str(trip_id), "place_ids": str(place_id)},
        ).status_code
        == 404
    )


def test_saved_places_page_shows_trip_controls_or_create_trip_hint(client, app, seeded_content):
    place_id = seeded_content["place"].id
    client.post(
        "/register",
        data={
            "email": "saved-ui@example.com",
            "password": "pw123456",
            "confirm": "pw123456",
        },
        follow_redirects=True,
    )
    client.post(f"/places/{place_id}/save")

    body = client.get("/saved").get_data(as_text=True)
    assert "Create a trip first to add saved places directly to an itinerary." in body
    assert 'form="saved-bulk-trip-form"' not in body

    client.post("/trips", data={"name": "UI Trip"}, follow_redirects=True)
    body = client.get("/saved").get_data(as_text=True)
    assert "Add selected places to trip" in body
    assert "UI Trip" in body
    assert 'form="saved-bulk-trip-form"' in body


def test_finder_pagination_reaches_beyond_previous_cap(client, app):
    with app.app_context():
        db = get_session(app)
        db.add_all([Place(name=f"Page Destination {i:03d}", city="Page City", state="PA") for i in range(205)])
        db.commit()

    first = client.get("/places?city=Page+City&sort=name")
    last = client.get("/places?city=Page+City&sort=name&page=9")
    first_body = first.get_data(as_text=True)
    last_body = last.get_data(as_text=True)
    assert first.status_code == last.status_code == 200
    assert "Showing 1–24 of 205 matches" in first_body
    assert "Page Destination 000" in first_body
    assert "Page Destination 024" not in first_body
    assert "Showing 193–205 of 205 matches" in last_body
    assert "Page Destination 204" in last_body
    assert "Page Destination 000" not in last_body
    assert "city=Page+City" in first_body
    assert "sort=name" in first_body


def test_finder_pagination_stable_on_tied_sort_values(client, app):
    with app.app_context():
        db = get_session(app)
        db.add_all([Place(name="Tied Page Destination", city="Tie City", state="PA") for _ in range(30)])
        db.commit()

    first = client.get("/places?city=Tie+City&page=1")
    second = client.get("/places?city=Tie+City&page=2")
    assert first.status_code == second.status_code == 200
    # IDs in detail links distinguish otherwise identical names.
    import re
    ids1 = set(re.findall(r'/places/(\\d+)', first.get_data(as_text=True)))
    ids2 = set(re.findall(r'/places/(\\d+)', second.get_data(as_text=True)))
    assert len(ids1) == 24
    assert len(ids2) == 6
    assert ids1.isdisjoint(ids2)


def test_finder_pagination_clamps_invalid_pages_and_preserves_filters(client, app):
    with app.app_context():
        db = get_session(app)
        db.add_all([
            Place(
                name=f"Featured Test {i:03d}",
                city="Filter City",
                state="NY",
                vlog_youtube_url="https://example.com/video",
            )
            for i in range(27)
        ])
        db.commit()

    filtered = client.get("/places?city=Filter+City&state=NY&vlog_status=featured&sort=newest&page=2")
    body = filtered.get_data(as_text=True)
    assert "Showing 25–27 of 27 matches" in body
    assert "vlog_status=featured" in body
    assert "sort=newest" in body
    assert "state=NY" in body
    for bad in ["-5", "not-a-page", "0"]:
        assert "Showing 1–24 of 27 matches" in client.get(
            f"/places?city=Filter+City&vlog_status=featured&page={bad}"
        ).get_data(as_text=True)
    assert "Showing 25–27 of 27 matches" in client.get(
        "/places?city=Filter+City&vlog_status=featured&page=99999"
    ).get_data(as_text=True)
    assert "Showing 0–0 of 0 matches" in client.get(
        "/places?city=No+Such+City"
    ).get_data(as_text=True)


def test_finder_saved_indicator_survives_pagination(client, app):
    with app.app_context():
        db = get_session(app)
        places = [Place(name=f"Saved Page Place {i:03d}", city="Saved City") for i in range(25)]
        db.add_all(places)
        db.commit()
        saved_id = places[-1].id

    client.post(
        "/register",
        data={"email": "saved-page@example.com", "password": "pw123456", "confirm": "pw123456"},
        follow_redirects=True,
    )
    client.post(f"/places/{saved_id}/save")
    body = client.get("/places?city=Saved+City&sort=name&page=2").get_data(as_text=True)
    assert f"/places/{saved_id}/unsave" in body
    assert 'name="_csrf_token"' in body
