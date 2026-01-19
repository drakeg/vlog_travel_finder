from sqlalchemy import create_engine, inspect


def test_sqlite_schema_upgrade_runs(tmp_path, monkeypatch):
    db_path = tmp_path / "schema.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SECRET_KEY", "test")

    from vlog_site import create_app

    app = create_app()
    app.config.update(TESTING=True)

    engine = create_engine(app.config["DATABASE_URL"], future=True)
    insp = inspect(engine)

    tables = set(insp.get_table_names())
    assert "place" in tables
    assert "category" in tables
    assert "admin_user" in tables
    assert "user" in tables
    assert "access_rule" in tables
    assert "site_setting" in tables
    assert "blog_post" in tables
    assert "contact_message" in tables
