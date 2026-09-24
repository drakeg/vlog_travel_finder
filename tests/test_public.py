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
