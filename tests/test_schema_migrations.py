from sqlalchemy import create_engine, text

from vlog_site.db import upgrade_sqlite_schema


def test_upgrade_version_11_adds_checklist_without_losing_trip(tmp_path):
    db_path = tmp_path / "migration.sqlite"
    engine = create_engine(f"sqlite:///{db_path}", future=True)

    with engine.begin() as conn:
        conn.connection.executescript(
            """
            CREATE TABLE user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE trip (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                notes TEXT NULL,
                start_date TEXT NULL,
                end_date TEXT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE trip_place (
                trip_id INTEGER NOT NULL,
                place_id INTEGER NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                notes TEXT NULL,
                planned_date TEXT NULL,
                planned_time TEXT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (trip_id, place_id)
            );

            CREATE TABLE site_setting (
                key TEXT PRIMARY KEY,
                value TEXT NULL
            );

            INSERT INTO user (email, password_hash, role)
            VALUES ('migration@example.com', 'hash', 'member');

            INSERT INTO trip (user_id, name, notes, start_date, end_date)
            VALUES (1, 'Existing Trip', 'Keep me', '2027-01-01', '2027-01-02');

            PRAGMA user_version = 11;
            """
        )

    upgrade_sqlite_schema(engine)

    with engine.begin() as conn:
        assert int(conn.execute(text("PRAGMA user_version")).scalar_one()) == 12
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
        assert "trip_checklist_item" in tables

        row = conn.execute(
            text("SELECT name, notes, start_date, end_date FROM trip WHERE id = 1")
        ).one()
        assert tuple(row) == (
            "Existing Trip",
            "Keep me",
            "2027-01-01",
            "2027-01-02",
        )

        conn.execute(
            text(
                """
                INSERT INTO trip_checklist_item (trip_id, text, completed)
                VALUES (1, 'Migrated checklist item', 0)
                """
            )
        )
        assert conn.execute(
            text("SELECT COUNT(*) FROM trip_checklist_item WHERE trip_id = 1")
        ).scalar_one() == 1
