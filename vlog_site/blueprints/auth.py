from __future__ import annotations

import functools
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_session
from ..models import User
from ..utils import clean_str


auth_bp = Blueprint("auth", __name__)


def _is_safe_next_url(next_url: str | None) -> bool:
    if not next_url:
        return False
    parsed = urlparse(next_url)
    return parsed.scheme == "" and parsed.netloc == ""


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id") is None:
            next_url = request.full_path if request.query_string else request.path
            return redirect(url_for("auth.login", next=next_url))
        return view(*args, **kwargs)

    return wrapped


@auth_bp.route("/register", methods=["GET", "POST"])
def register() -> str:
    db = get_session(current_app)
    next_url = request.args.get("next")

    if request.method == "POST":
        email = clean_str(request.form.get("email"))
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        if not email or not password:
            flash("Email and password are required", "error")
        elif password != confirm:
            flash("Passwords do not match", "error")
        else:
            existing = db.execute(select(User).where(User.email == email)).scalars().first()
            if existing:
                flash("An account with that email already exists", "error")
            else:
                user = User(email=email, password_hash=generate_password_hash(password), role="member")
                db.add(user)
                db.commit()
                session.clear()
                session["user_id"] = user.id
                if _is_safe_next_url(next_url):
                    return redirect(next_url)
                return redirect(url_for("public.home"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login() -> str:
    db = get_session(current_app)
    next_url = request.args.get("next")

    if request.method == "POST":
        email = clean_str(request.form.get("email"))
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Email and password are required", "error")
        else:
            user = db.execute(select(User).where(User.email == email)).scalars().first()
            if user and check_password_hash(user.password_hash, password):
                session.clear()
                session["user_id"] = user.id
                if _is_safe_next_url(next_url):
                    return redirect(next_url)
                return redirect(url_for("public.home"))
            flash("Invalid credentials", "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
def logout() -> str:
    session.clear()
    return redirect(url_for("public.home"))
