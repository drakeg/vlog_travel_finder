import os
from datetime import datetime, timedelta, timezone
import secrets

import pytest
from werkzeug.security import generate_password_hash

from vlog_site import create_app
from vlog_site.db import get_session
from vlog_site.models import BlogPost, Category, ContactMessage, Place, User


@pytest.fixture()
def app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SECRET_KEY", "test")

    app = create_app()
    app.config.update(TESTING=True)

    admin_password = secrets.token_urlsafe(16)
    app.config["TEST_ADMIN_PASSWORD"] = admin_password

    # Seed a default admin user
    with app.app_context():
        db = get_session(app)
        if db.query(User).count() == 0:
            db.add(
                User(
                    email="admin@example.com",
                    password_hash=generate_password_hash(admin_password),
                    role="admin",
                )
            )
            db.commit()

    return app


@pytest.fixture()
def admin_password(app):
    return app.config["TEST_ADMIN_PASSWORD"]


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    with app.app_context():
        yield get_session(app)


@pytest.fixture()
def seeded_content(db):
    cat = Category(name="Museums")
    db.add(cat)
    db.commit()

    place = Place(name="Test Place", category_id=cat.id, city="Testville", state="TS")
    db.add(place)

    past = datetime.now(timezone.utc) - timedelta(days=1)
    future = datetime.now(timezone.utc) + timedelta(days=1)

    db.add(
        BlogPost(
            title="Published Past",
            slug="published-past",
            content_md="Hello",
            status="published",
            publish_at=past.strftime("%Y-%m-%d %H:%M:%S"),
        )
    )
    db.add(
        BlogPost(
            title="Published Future",
            slug="published-future",
            content_md="Hello",
            status="published",
            publish_at=future.strftime("%Y-%m-%d %H:%M:%S"),
        )
    )
    db.add(
        BlogPost(
            title="Draft",
            slug="draft",
            content_md="Hello",
            status="draft",
            publish_at=None,
        )
    )

    db.add(
        ContactMessage(
            name="Alice",
            email="alice@example.com",
            subject="Hi",
            message="Hello there",
            answered_at=None,
        )
    )

    db.commit()
    return {"category": cat, "place": place}
