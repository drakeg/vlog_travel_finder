import os
from flask import Flask

from .db import init_db
from .blueprints.admin import admin_bp
from .blueprints.auth import auth_bp
from .blueprints.public import public_bp
from .context import inject_globals


APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SQLITE_PATH = os.path.join(os.path.dirname(APP_DIR), "instance", "vlog_site.sqlite")
REPO_DIR = os.path.dirname(APP_DIR)


def create_app() -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=os.path.join(REPO_DIR, "templates"),
        static_folder=os.path.join(REPO_DIR, "static"),
    )
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        DATABASE_URL=os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}"),
    )

    init_db(app)

    @app.cli.command("init-db")
    def init_db_command() -> None:
        init_db(app)
        print("Database is ready")

    @app.cli.command("upgrade-db")
    def upgrade_db_command() -> None:
        init_db(app)
        print("Database schema is up to date")

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.context_processor(inject_globals)

    return app
