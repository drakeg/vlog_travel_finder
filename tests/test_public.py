def test_home_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200


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
