from __future__ import annotations

from typing import Generator
from urllib.parse import urlparse

from flask import Flask, g
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def _is_sqlite(database_url: str) -> bool:
    return database_url.startswith("sqlite:")


def _configure_sqlite(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        except Exception:
            pass


def get_engine(app: Flask) -> Engine:
    if "engine" not in g:
        database_url = app.config["DATABASE_URL"]
        engine = create_engine(database_url, future=True)
        if _is_sqlite(database_url):
            _configure_sqlite(engine)
        g.engine = engine
    return g.engine


def get_session(app: Flask) -> Session:
    if "session" not in g:
        engine = get_engine(app)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        g.session = SessionLocal()
    return g.session


def close_db(_exc=None) -> None:
    session: Session | None = g.pop("session", None)
    if session is not None:
        session.close()
    g.pop("engine", None)


def init_db(app: Flask) -> None:
    app.teardown_appcontext(close_db)

    database_url = app.config["DATABASE_URL"]
    engine = create_engine(database_url, future=True)
    if _is_sqlite(database_url):
        _configure_sqlite(engine)
        upgrade_sqlite_schema(engine)
    else:
        Base.metadata.create_all(engine)


def _get_user_version(conn) -> int:
    return int(conn.execute(text("PRAGMA user_version")).scalar_one())


def _set_user_version(conn, version: int) -> None:
    conn.execute(text(f"PRAGMA user_version = {int(version)}"))


def upgrade_sqlite_schema(engine: Engine) -> None:
    # Keep your existing safe, versioned SQLite migration strategy.
    with engine.begin() as conn:
        version = _get_user_version(conn)

        # Infer version for existing DBs without PRAGMA user_version set.
        if version == 0:
            tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
            if "site_setting" in tables:
                version = 2
            elif {"place", "category", "admin_user"}.issubset(tables):
                version = 1
            else:
                version = 0
            _set_user_version(conn, version)

        latest_version = 5
        while version < latest_version:
            if version == 0:
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS admin_user (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            created_at TEXT NOT NULL DEFAULT (datetime('now'))
                        );

                        CREATE TABLE IF NOT EXISTS category (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT UNIQUE NOT NULL
                        );

                        CREATE TABLE IF NOT EXISTS place (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL,
                            category_id INTEGER NULL,
                            address TEXT NULL,
                            city TEXT NULL,
                            state TEXT NULL,
                            zipcode TEXT NULL,
                            latitude REAL NULL,
                            longitude REAL NULL,
                            website_url TEXT NULL,
                            youtube_url TEXT NULL,
                            tiktok_url TEXT NULL,
                            notes TEXT NULL,
                            created_at TEXT NOT NULL DEFAULT (datetime('now')),
                            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                            FOREIGN KEY (category_id) REFERENCES category (id) ON DELETE SET NULL
                        );

                        CREATE INDEX IF NOT EXISTS idx_place_city ON place(city);
                        CREATE INDEX IF NOT EXISTS idx_place_state ON place(state);
                        CREATE INDEX IF NOT EXISTS idx_place_category ON place(category_id);
                        """
                    )
                )
                version = 1
                _set_user_version(conn, version)
                continue

            if version == 1:
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS site_setting (
                            key TEXT PRIMARY KEY,
                            value TEXT NULL
                        );
                        """
                    )
                )
                conn.execute(
                    text(
                        "INSERT OR IGNORE INTO site_setting (key, value) VALUES ('contact_email', NULL)"
                    )
                )
                conn.execute(
                    text(
                        "INSERT OR IGNORE INTO site_setting (key, value) VALUES ('contact_phone', NULL)"
                    )
                )
                version = 2
                _set_user_version(conn, version)
                continue

            if version == 2:
                cols = {
                    r[1]
                    for r in conn.execute(text("PRAGMA table_info(place)"))
                    if r[1] is not None
                }

                def _add_col(col: str) -> None:
                    if col not in cols:
                        conn.execute(text(f"ALTER TABLE place ADD COLUMN {col} TEXT NULL"))

                _add_col("venue_website_url")
                _add_col("venue_youtube_url")
                _add_col("venue_tiktok_url")
                _add_col("venue_instagram_url")
                _add_col("venue_facebook_url")
                _add_col("vlog_youtube_url")
                _add_col("vlog_tiktok_url")
                _add_col("vlog_instagram_url")

                conn.execute(
                    text(
                        """
                        UPDATE place
                        SET
                            venue_website_url = COALESCE(venue_website_url, website_url),
                            venue_youtube_url = COALESCE(venue_youtube_url, youtube_url),
                            venue_tiktok_url = COALESCE(venue_tiktok_url, tiktok_url)
                        """
                    )
                )

                version = 3
                _set_user_version(conn, version)
                continue

            if version == 3:
                conn.connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS blog_post (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        slug TEXT UNIQUE NOT NULL,
                        content_md TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'draft',
                        publish_at TEXT NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );

                    CREATE INDEX IF NOT EXISTS idx_blog_post_status_publish_at ON blog_post(status, publish_at);

                    CREATE TABLE IF NOT EXISTS contact_message (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        email TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        message TEXT NOT NULL,
                        answered_at TEXT NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );

                    CREATE INDEX IF NOT EXISTS idx_contact_message_answered_at ON contact_message(answered_at);
                    """
                )

                for k in [
                    "featured_youtube_url",
                    "smtp_host",
                    "smtp_port",
                    "smtp_username",
                    "smtp_password",
                    "smtp_from",
                    "smtp_to",
                ]:
                    conn.execute(text("INSERT OR IGNORE INTO site_setting (key, value) VALUES (:k, NULL)"), {"k": k})

                version = 4
                _set_user_version(conn, version)
                continue

            if version == 4:
                # Site-wide auth + access rules.
                conn.connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS user (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'member',
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );

                    CREATE TABLE IF NOT EXISTS access_rule (
                        feature TEXT PRIMARY KEY,
                        anonymous_access INTEGER NOT NULL DEFAULT 1
                    );
                    """
                )

                # Migrate existing admin users into the new user table as admins.
                try:
                    admin_rows = conn.execute(text("SELECT username, password_hash, created_at FROM admin_user")).all()
                except Exception:
                    admin_rows = []

                for username, password_hash, created_at in admin_rows:
                    # Historically we used "username"; treat it as the login identifier.
                    conn.execute(
                        text(
                            """
                            INSERT OR IGNORE INTO user (email, password_hash, role, created_at)
                            VALUES (:email, :password_hash, 'admin', COALESCE(:created_at, datetime('now')))
                            """
                        ),
                        {"email": username, "password_hash": password_hash, "created_at": created_at},
                    )

                # Default rules: anonymous access allowed for all known features.
                for feature in ["home", "places", "blog", "contact", "about"]:
                    conn.execute(
                        text(
                            """
                            INSERT OR IGNORE INTO access_rule (feature, anonymous_access)
                            VALUES (:feature, 1)
                            """
                        ),
                        {"feature": feature},
                    )

                version = 5
                _set_user_version(conn, version)
                continue

            raise RuntimeError(f"Unsupported schema version: {version}")
