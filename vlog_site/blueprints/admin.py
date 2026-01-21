from __future__ import annotations

import functools
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, select, text
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from ..db import get_session
from ..models import AccessRule, BlogPost, Category, ContactMessage, PageView, Place, User
from ..services.mail_service import is_smtp_configured, send_reply_email_if_configured
from ..services.settings_service import get_setting, set_setting
from ..utils import clean_str, coerce_float, coerce_publish_at, slugify


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


ACCESS_FEATURES: list[str] = ["home", "places", "blog", "contact", "about"]


def is_admin() -> bool:
    user_id = session.get("user_id")
    if user_id is None:
        return False
    db = get_session(current_app)
    user = db.execute(select(User).where(User.id == user_id)).scalars().first()
    return user is not None and user.role == "admin"


def _is_safe_next_url(next_url: str | None) -> bool:
    if not next_url:
        return False
    parsed = urlparse(next_url)
    return parsed.scheme == "" and parsed.netloc == ""


@admin_bp.before_request
def _admin_auth_gate():
    if is_admin():
        return None

    # Allow reaching the admin index (redirects to site login).
    if request.endpoint in {"admin.admin_login", "admin.admin_index"}:
        return None

    flash("Please log in to access the admin area", "error")
    next_url = request.full_path if request.query_string else request.path
    return redirect(url_for("auth.login", next=next_url))


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not is_admin():
            flash("Please log in to access the admin area", "error")
            next_url = request.full_path if request.query_string else request.path
            return redirect(url_for("auth.login", next=next_url))
        return view(*args, **kwargs)

    return wrapped


@admin_bp.route("")
@admin_bp.route("/")
def admin_index() -> str:
    if not is_admin():
        return redirect(url_for("auth.login", next="/admin"))
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login() -> str:
    next_url = request.args.get("next") or "/admin"
    if _is_safe_next_url(next_url):
        return redirect(url_for("auth.login", next=next_url))
    return redirect(url_for("auth.login", next="/admin"))


@admin_bp.route("/logout", methods=["POST"])
def admin_logout() -> str:
    session.clear()
    return redirect(url_for("public.home"))


@admin_bp.route("/places")
@admin_required
def admin_places() -> str:
    db = get_session(current_app)

    rows = (
        db.execute(
            select(Place)
            .order_by(text("updated_at DESC"), Place.id.desc())
            .limit(500)
        )
        .scalars()
        .all()
    )

    # Template expects dict-like rows; provide minimal mapping by building dicts
    places = [
        {
            "id": p.id,
            "name": p.name,
            "city": p.city,
            "state": p.state,
            "category_name": p.category.name if getattr(p, "category", None) else None,
        }
        for p in rows
    ]

    return render_template("admin/places.html", places=places)


@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def admin_settings() -> str:
    db = get_session(current_app)

    if request.method == "POST":
        site_name = clean_str(request.form.get("site_name"))
        theme_primary = clean_str(request.form.get("theme_primary"))
        theme_secondary = clean_str(request.form.get("theme_secondary"))
        hero_image_alt = clean_str(request.form.get("hero_image_alt"))
        contact_email = clean_str(request.form.get("contact_email"))
        contact_phone = clean_str(request.form.get("contact_phone"))
        featured_youtube_url = clean_str(request.form.get("featured_youtube_url"))
        smtp_host = clean_str(request.form.get("smtp_host"))
        smtp_port = clean_str(request.form.get("smtp_port"))
        smtp_username = clean_str(request.form.get("smtp_username"))
        smtp_password = clean_str(request.form.get("smtp_password"))
        smtp_from = clean_str(request.form.get("smtp_from"))
        smtp_to = clean_str(request.form.get("smtp_to"))

        set_setting(db, "site_name", site_name)
        set_setting(db, "theme_primary", theme_primary)
        set_setting(db, "theme_secondary", theme_secondary)
        set_setting(db, "hero_image_alt", hero_image_alt)
        set_setting(db, "contact_email", contact_email)
        set_setting(db, "contact_phone", contact_phone)
        set_setting(db, "featured_youtube_url", featured_youtube_url)
        set_setting(db, "smtp_host", smtp_host)
        set_setting(db, "smtp_port", smtp_port)
        set_setting(db, "smtp_username", smtp_username)
        set_setting(db, "smtp_password", smtp_password)
        set_setting(db, "smtp_from", smtp_from)
        set_setting(db, "smtp_to", smtp_to)

        uploaded = request.files.get("hero_image_file")
        if uploaded is not None and uploaded.filename:
            filename = secure_filename(uploaded.filename)
            _, ext = os.path.splitext(filename.lower())
            if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
                flash("Hero image must be a JPG, PNG, WEBP, or GIF", "error")
                return redirect(url_for("admin.admin_settings"))

            upload_dir = os.path.join(current_app.instance_path, "uploads")
            os.makedirs(upload_dir, exist_ok=True)

            stored_name = f"hero{ext}"
            uploaded.save(os.path.join(upload_dir, stored_name))
            set_setting(db, "hero_image_filename", stored_name)

        uploaded = request.files.get("logo_file")
        if uploaded is not None and uploaded.filename:
            filename = secure_filename(uploaded.filename)
            _, ext = os.path.splitext(filename.lower())
            if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}:
                flash("Logo must be a JPG, PNG, WEBP, GIF, or SVG", "error")
                return redirect(url_for("admin.admin_settings"))

            upload_dir = os.path.join(current_app.instance_path, "uploads")
            os.makedirs(upload_dir, exist_ok=True)

            stored_name = f"logo{ext}"
            uploaded.save(os.path.join(upload_dir, stored_name))
            set_setting(db, "logo_filename", stored_name)

        db.commit()
        flash("Settings saved", "info")
        return redirect(url_for("admin.admin_settings"))

    return render_template(
        "admin/settings.html",
        site_name=get_setting(db, "site_name"),
        theme_primary=get_setting(db, "theme_primary"),
        theme_secondary=get_setting(db, "theme_secondary"),
        hero_image_filename=get_setting(db, "hero_image_filename"),
        hero_image_alt=get_setting(db, "hero_image_alt"),
        logo_filename=get_setting(db, "logo_filename"),
        contact_email=get_setting(db, "contact_email"),
        contact_phone=get_setting(db, "contact_phone"),
        featured_youtube_url=get_setting(db, "featured_youtube_url"),
        smtp_host=get_setting(db, "smtp_host"),
        smtp_port=get_setting(db, "smtp_port"),
        smtp_username=get_setting(db, "smtp_username"),
        smtp_password=get_setting(db, "smtp_password"),
        smtp_from=get_setting(db, "smtp_from"),
        smtp_to=get_setting(db, "smtp_to"),
    )


@admin_bp.route("/access-control", methods=["GET", "POST"])
@admin_required
def admin_access_control() -> str:
    db = get_session(current_app)

    if request.method == "POST":
        for feature in ACCESS_FEATURES:
            allow = request.form.get(f"anon_{feature}") == "on"
            rule = db.get(AccessRule, feature)
            if rule is None:
                db.add(AccessRule(feature=feature, anonymous_access=allow))
            else:
                rule.anonymous_access = allow
        db.commit()
        flash("Access control updated", "info")
        return redirect(url_for("admin.admin_access_control"))

    rules = {r.feature: r for r in db.execute(select(AccessRule)).scalars().all()}
    features = [
        {
            "feature": f,
            "anonymous_access": (rules.get(f).anonymous_access if rules.get(f) is not None else True),
        }
        for f in ACCESS_FEATURES
    ]
    return render_template("admin/access_control.html", features=features)


@admin_bp.route("/preview/anonymous", methods=["POST"])
@admin_required
def admin_preview_anonymous() -> str:
    session["anonymous_preview"] = True
    return redirect(request.referrer or url_for("public.home"))


@admin_bp.route("/preview/stop", methods=["POST"])
@admin_required
def admin_preview_stop() -> str:
    session.pop("anonymous_preview", None)
    return redirect(request.referrer or url_for("public.home"))


@admin_bp.route("/categories", methods=["GET", "POST"])
@admin_required
def admin_categories() -> str:
    db = get_session(current_app)

    if request.method == "POST":
        name = clean_str(request.form.get("name"))
        if not name:
            flash("Category name is required", "error")
        else:
            existing = db.execute(select(Category).where(Category.name == name)).scalars().first()
            if existing:
                flash("Category already exists", "error")
            else:
                db.add(Category(name=name))
                db.commit()
                return redirect(url_for("admin.admin_categories"))

    categories = db.execute(select(Category).order_by(Category.name.asc())).scalars().all()
    return render_template("admin/categories.html", categories=categories)


@admin_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def admin_category_delete(category_id: int) -> str:
    db = get_session(current_app)
    cat = db.get(Category, category_id)
    if cat:
        db.delete(cat)
        db.commit()
    return redirect(url_for("admin.admin_categories"))


@admin_bp.route("/places/new", methods=["GET", "POST"])
@admin_required
def admin_place_new() -> str:
    db = get_session(current_app)
    categories = db.execute(select(Category).order_by(Category.name.asc())).scalars().all()

    if request.method == "POST":
        name = clean_str(request.form.get("name"))
        category_id_raw = clean_str(request.form.get("category_id"))
        category_id = int(category_id_raw) if category_id_raw else None

        if not name:
            flash("Name is required", "error")
        else:
            place = Place(
                name=name,
                category_id=category_id,
                address=clean_str(request.form.get("address")),
                city=clean_str(request.form.get("city")),
                state=clean_str(request.form.get("state")),
                zipcode=clean_str(request.form.get("zipcode")),
                latitude=coerce_float(request.form.get("latitude")),
                longitude=coerce_float(request.form.get("longitude")),
                venue_website_url=clean_str(request.form.get("venue_website_url")),
                venue_youtube_url=clean_str(request.form.get("venue_youtube_url")),
                venue_tiktok_url=clean_str(request.form.get("venue_tiktok_url")),
                venue_instagram_url=clean_str(request.form.get("venue_instagram_url")),
                venue_facebook_url=clean_str(request.form.get("venue_facebook_url")),
                vlog_youtube_url=clean_str(request.form.get("vlog_youtube_url")),
                vlog_tiktok_url=clean_str(request.form.get("vlog_tiktok_url")),
                vlog_instagram_url=clean_str(request.form.get("vlog_instagram_url")),
                notes=clean_str(request.form.get("notes")),
            )
            db.add(place)
            db.commit()
            return redirect(url_for("admin.admin_places"))

    return render_template("admin/place_form.html", place=None, categories=categories)


@admin_bp.route("/places/<int:place_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_place_edit(place_id: int) -> str:
    db = get_session(current_app)
    categories = db.execute(select(Category).order_by(Category.name.asc())).scalars().all()
    place = db.get(Place, place_id)
    if place is None:
        abort(404)

    if request.method == "POST":
        name = clean_str(request.form.get("name"))
        category_id_raw = clean_str(request.form.get("category_id"))
        category_id = int(category_id_raw) if category_id_raw else None

        if not name:
            flash("Name is required", "error")
        else:
            place.name = name
            place.category_id = category_id
            place.address = clean_str(request.form.get("address"))
            place.city = clean_str(request.form.get("city"))
            place.state = clean_str(request.form.get("state"))
            place.zipcode = clean_str(request.form.get("zipcode"))
            place.latitude = coerce_float(request.form.get("latitude"))
            place.longitude = coerce_float(request.form.get("longitude"))
            place.venue_website_url = clean_str(request.form.get("venue_website_url"))
            place.venue_youtube_url = clean_str(request.form.get("venue_youtube_url"))
            place.venue_tiktok_url = clean_str(request.form.get("venue_tiktok_url"))
            place.venue_instagram_url = clean_str(request.form.get("venue_instagram_url"))
            place.venue_facebook_url = clean_str(request.form.get("venue_facebook_url"))
            place.vlog_youtube_url = clean_str(request.form.get("vlog_youtube_url"))
            place.vlog_tiktok_url = clean_str(request.form.get("vlog_tiktok_url"))
            place.vlog_instagram_url = clean_str(request.form.get("vlog_instagram_url"))
            place.notes = clean_str(request.form.get("notes"))
            db.commit()
            return redirect(url_for("admin.admin_places"))

    return render_template("admin/place_form.html", place=place, categories=categories)


@admin_bp.route("/places/<int:place_id>/delete", methods=["POST"])
@admin_required
def admin_place_delete(place_id: int) -> str:
    db = get_session(current_app)
    place = db.get(Place, place_id)
    if place:
        db.delete(place)
        db.commit()
    return redirect(url_for("admin.admin_places"))


@admin_bp.route("/dashboard")
@admin_required
def admin_dashboard() -> str:
    db = get_session(current_app)

    total_views = db.execute(select(func.count()).select_from(PageView)).scalar_one()

    last_7 = db.execute(
        select(func.count()).select_from(PageView).where(text("created_at >= datetime('now','-7 days')"))
    ).scalar_one()

    last_30 = db.execute(
        select(func.count()).select_from(PageView).where(text("created_at >= datetime('now','-30 days')"))
    ).scalar_one()

    top_pages = db.execute(
        select(PageView.path, text("COUNT(1) as c"))
        .group_by(PageView.path)
        .order_by(text("c DESC"))
        .limit(10)
    ).all()

    top_referrers = db.execute(
        select(PageView.referrer, text("COUNT(1) as c"))
        .where(PageView.referrer.is_not(None))
        .group_by(PageView.referrer)
        .order_by(text("c DESC"))
        .limit(10)
    ).all()

    top_countries = db.execute(
        select(PageView.country, text("COUNT(1) as c"))
        .where(PageView.country.is_not(None))
        .group_by(PageView.country)
        .order_by(text("c DESC"))
        .limit(10)
    ).all()

    daily = db.execute(
        select(text("substr(created_at, 1, 10) as day"), text("COUNT(1) as c"))
        .select_from(PageView)
        .where(text("created_at >= datetime('now','-14 days')"))
        .group_by(text("day"))
        .order_by(text("day ASC"))
    ).all()

    return render_template(
        "admin/dashboard.html",
        total_views=int(total_views or 0),
        last_7=int(last_7 or 0),
        last_30=int(last_30 or 0),
        top_pages=[{"path": r[0], "count": int(r[1] or 0)} for r in top_pages],
        top_referrers=[{"referrer": r[0], "count": int(r[1] or 0)} for r in top_referrers],
        top_countries=[{"country": r[0], "count": int(r[1] or 0)} for r in top_countries],
        daily=[{"day": r[0], "count": int(r[1] or 0)} for r in daily],
    )


@admin_bp.route("/posts")
@admin_required
def admin_posts() -> str:
    db = get_session(current_app)
    rows = db.execute(select(BlogPost).order_by(text("updated_at DESC"), BlogPost.id.desc())).scalars().all()
    posts = [
        {
            "id": p.id,
            "title": p.title,
            "slug": p.slug,
            "status": p.status,
            "publish_at": p.publish_at,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        }
        for p in rows
    ]
    return render_template("admin/posts.html", posts=posts)


@admin_bp.route("/posts/new", methods=["GET", "POST"])
@admin_required
def admin_post_new() -> str:
    db = get_session(current_app)

    if request.method == "POST":
        title = clean_str(request.form.get("title"))
        slug = clean_str(request.form.get("slug"))
        content_md = request.form.get("content_md") or ""
        status = clean_str(request.form.get("status")) or "draft"
        publish_at = coerce_publish_at(request.form.get("publish_at"))

        if not title:
            flash("Title is required", "error")
        else:
            final_slug = slug or slugify(title)
            existing = db.execute(select(BlogPost).where(BlogPost.slug == final_slug)).scalars().first()
            if existing:
                flash("Slug already exists", "error")
            else:
                post = BlogPost(
                    title=title,
                    slug=final_slug,
                    content_md=content_md,
                    status=status,
                    publish_at=publish_at,
                )
                db.add(post)
                db.commit()
                return redirect(url_for("admin.admin_posts"))

    return render_template("admin/post_form.html", post=None)


@admin_bp.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_post_edit(post_id: int) -> str:
    db = get_session(current_app)
    post = db.get(BlogPost, post_id)
    if post is None:
        abort(404)

    if request.method == "POST":
        title = clean_str(request.form.get("title"))
        slug = clean_str(request.form.get("slug"))
        content_md = request.form.get("content_md") or ""
        status = clean_str(request.form.get("status")) or "draft"
        publish_at = coerce_publish_at(request.form.get("publish_at"))

        if not title or not slug:
            flash("Title and slug are required", "error")
        else:
            existing = (
                db.execute(select(BlogPost).where(BlogPost.slug == slug, BlogPost.id != post_id))
                .scalars()
                .first()
            )
            if existing:
                flash("Slug already exists", "error")
            else:
                post.title = title
                post.slug = slug
                post.content_md = content_md
                post.status = status
                post.publish_at = publish_at
                db.commit()
                return redirect(url_for("admin.admin_posts"))

    return render_template("admin/post_form.html", post=post)


@admin_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@admin_required
def admin_post_delete(post_id: int) -> str:
    db = get_session(current_app)
    post = db.get(BlogPost, post_id)
    if post:
        db.delete(post)
        db.commit()
    return redirect(url_for("admin.admin_posts"))


@admin_bp.route("/messages")
@admin_required
def admin_messages() -> str:
    db = get_session(current_app)
    smtp_configured = is_smtp_configured(db=db)
    rows = (
        db.execute(
            select(ContactMessage).order_by(
                text("CASE WHEN answered_at IS NULL THEN 0 ELSE 1 END"),
                text("created_at DESC"),
                ContactMessage.id.desc(),
            )
        )
        .scalars()
        .all()
    )
    messages = [
        {
            "id": m.id,
            "name": m.name,
            "email": m.email,
            "subject": m.subject,
            "message": m.message,
            "answered_at": m.answered_at,
            "created_at": m.created_at,
        }
        for m in rows
    ]
    return render_template("admin/messages.html", messages=messages, smtp_configured=smtp_configured)


@admin_bp.route("/messages/<int:message_id>/reply", methods=["GET", "POST"])
@admin_required
def admin_message_reply(message_id: int) -> str:
    db = get_session(current_app)
    msg = db.get(ContactMessage, message_id)
    if msg is None:
        abort(404)

    smtp_configured = is_smtp_configured(db=db)
    if request.method == "POST":
        if not smtp_configured:
            flash("SMTP is not configured. Configure it in Site settings to send replies.", "error")
            return redirect(url_for("admin.admin_messages"))

        subject = clean_str(request.form.get("subject")) or f"Re: {msg.subject}"
        body = request.form.get("body") or ""
        if not body.strip():
            flash("Reply message is required", "error")
        else:
            sent = send_reply_email_if_configured(
                db=db,
                to_addr=msg.email,
                subject=subject,
                reply_body=body,
                original_message=msg.message,
            )
            if sent:
                msg.answered_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                db.commit()
                flash("Reply sent", "info")
                return redirect(url_for("admin.admin_messages"))
            flash("SMTP is not configured. Configure it in Site settings to send replies.", "error")

    return render_template(
        "admin/message_reply.html",
        smtp_configured=smtp_configured,
        message={
            "id": msg.id,
            "name": msg.name,
            "email": msg.email,
            "subject": msg.subject,
            "message": msg.message,
            "created_at": msg.created_at,
        },
        default_subject=f"Re: {msg.subject}",
    )


@admin_bp.route("/messages/<int:message_id>/toggle-answered", methods=["POST"])
@admin_required
def admin_message_toggle_answered(message_id: int) -> str:
    db = get_session(current_app)
    msg = db.get(ContactMessage, message_id)
    if msg is None:
        abort(404)

    msg.answered_at = (
        None
        if msg.answered_at
        else datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    db.commit()
    return redirect(url_for("admin.admin_messages"))


@admin_bp.cli.command("create-admin")
def create_admin_command() -> None:
    db = get_session(current_app)
    username = input("Admin email: ").strip()
    password = input("Admin password: ").strip()
    if not username or not password:
        raise SystemExit("username/password required")

    existing = db.execute(select(User).where(User.email == username)).scalars().first()
    if existing:
        raise SystemExit("username already exists")

    db.add(User(email=username, password_hash=generate_password_hash(password), role="admin"))
    db.commit()
    print("Admin user created")


@admin_bp.cli.command("upgrade-db")
def upgrade_db_command() -> None:
    # SQLite migrations happen at startup; this is kept for CLI parity.
    print("Database is ready")
