import os
import click
import hashlib
import hmac
from flask import Flask
from flask import request
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from .db import init_db
from .db import get_session
from .blueprints.admin import admin_bp
from .blueprints.auth import auth_bp
from .blueprints.public import public_bp
from .context import inject_globals
from .models import PageView, User


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

    @app.after_request
    def _log_page_view(response):
        try:
            path = request.path or ""
            if (
                path.startswith("/admin")
                or path.startswith("/static")
                or path.startswith("/uploads")
                or path == "/favicon.ico"
            ):
                return response

            if request.method not in {"GET", "HEAD"}:
                return response

            db = get_session(app)

            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
            ip = (ip.split(",")[0] if ip else "").strip()
            secret = (app.config.get("SECRET_KEY") or "").encode("utf-8")
            ip_hash = None
            if ip and secret:
                ip_hash = hmac.new(secret, ip.encode("utf-8"), hashlib.sha256).hexdigest()

            country = request.headers.get("CF-IPCountry") or request.headers.get("X-Country")
            if country:
                country = country.strip()[:16]

            db.add(
                PageView(
                    path=path,
                    method=request.method,
                    status_code=int(getattr(response, "status_code", 0) or 0),
                    referrer=(request.referrer or "")[:500] or None,
                    user_agent=(request.headers.get("User-Agent") or "")[:500] or None,
                    ip_hash=ip_hash,
                    country=country,
                )
            )
            db.commit()
        except Exception:
            pass
        return response

    @app.cli.command("init-db")
    def init_db_command() -> None:
        init_db(app)
        print("Database is ready")

    @app.cli.command("upgrade-db")
    def upgrade_db_command() -> None:
        init_db(app)
        print("Database schema is up to date")

    @app.cli.command("create-admin")
    def create_admin_command() -> None:
        db = get_session(app)
        email = input("Admin email: ").strip()
        password = input("Admin password: ").strip()
        if not email or not password:
            raise SystemExit("email/password required")

        existing = db.execute(select(User).where(User.email == email)).scalars().first()
        if existing:
            raise SystemExit("email already exists")

        db.add(User(email=email, password_hash=generate_password_hash(password), role="admin"))
        db.commit()
        print("Admin user created")

    @app.cli.command("promote-admin")
    @click.argument("email")
    def promote_admin_command(email: str) -> None:
        db = get_session(app)
        email = (email or "").strip()
        if not email:
            raise SystemExit("email required")

        user = db.execute(select(User).where(User.email == email)).scalars().first()
        if user is None:
            raise SystemExit("user not found")

        user.role = "admin"
        db.commit()
        print("User promoted to admin")

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.context_processor(inject_globals)

    return app
