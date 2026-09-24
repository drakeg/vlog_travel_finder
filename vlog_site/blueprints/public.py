from __future__ import annotations

import os

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask import send_from_directory
from sqlalchemy import or_, select, text

from ..access_control import require_feature
from ..db import get_session
from ..models import BlogPost, Category, ContactMessage, Place, SavedPlace
from ..services.mail_service import send_contact_email_if_configured
from ..services.markdown_service import render_markdown
from ..services.settings_service import get_setting
from ..services.youtube_service import get_channel_url, get_latest_video, normalize_featured_embed_url
from ..blueprints.auth import login_required
from ..utils import clean_str


public_bp = Blueprint("public", __name__)


def _safe_local_next(value: str | None, fallback: str) -> str:
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return fallback


@public_bp.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    upload_dir = os.path.join(current_app.instance_path, "uploads")
    return send_from_directory(upload_dir, filename)


@public_bp.route("/")
@require_feature("home")
def home() -> str:
    db = get_session(current_app)
    featured_youtube_url = normalize_featured_embed_url(get_setting(db, "featured_youtube_url"))
    featured_video_id = None
    featured_video_url = None
    featured_thumbnail_url = None
    if featured_youtube_url and "/embed/" in featured_youtube_url:
        featured_video_id = featured_youtube_url.split("/embed/", 1)[1].split("?", 1)[0].split("&", 1)[0].strip("/")
        if featured_video_id:
            featured_video_url = f"https://www.youtube.com/watch?v={featured_video_id}"
            featured_thumbnail_url = f"https://i.ytimg.com/vi/{featured_video_id}/hqdefault.jpg"
    latest_video = get_latest_video(db=db)
    youtube_channel_url = get_channel_url(db=db)
    hero_image_filename = get_setting(db, "hero_image_filename")
    hero_image_url = (
        url_for("public.uploaded_file", filename=hero_image_filename)
        if hero_image_filename
        else get_setting(db, "hero_image_url")
    )
    hero_image_alt = get_setting(db, "hero_image_alt")

    posts = (
        db.execute(
            select(BlogPost)
            .where(
                BlogPost.status == "published",
                or_(BlogPost.publish_at.is_(None), BlogPost.publish_at <= text("datetime('now')")),
            )
            .order_by(text("COALESCE(publish_at, created_at) DESC"), BlogPost.id.desc())
            .limit(6)
        )
        .scalars()
        .all()
    )

    return render_template(
        "public/home.html",
        featured_youtube_url=featured_youtube_url,
        featured_video_id=featured_video_id,
        featured_video_url=featured_video_url,
        featured_thumbnail_url=featured_thumbnail_url,
        latest_video=latest_video,
        youtube_channel_url=youtube_channel_url,
        hero_image_url=hero_image_url,
        hero_image_alt=hero_image_alt,
        posts=posts,
    )


@public_bp.route("/places")
@require_feature("places")
def places() -> str:
    db = get_session(current_app)

    q = clean_str(request.args.get("q"))
    city = clean_str(request.args.get("city"))
    state = clean_str(request.args.get("state"))
    category_id_raw = clean_str(request.args.get("category_id"))
    vlog_status = clean_str(request.args.get("vlog_status"))
    sort = clean_str(request.args.get("sort")) or "location"
    try:
        category_id = int(category_id_raw) if category_id_raw else None
    except ValueError:
        category_id = None

    stmt = select(Place)
    if sort == "name":
        stmt = stmt.order_by(Place.name.asc(), text("COALESCE(state, '')"), text("COALESCE(city, '')"))
    elif sort == "newest":
        stmt = stmt.order_by(Place.created_at.desc(), Place.id.desc())
    else:
        sort = "location"
        stmt = stmt.order_by(text("COALESCE(state, '')"), text("COALESCE(city, '')"), Place.name.asc())
    stmt = stmt.limit(200)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Place.name.like(like),
                Place.city.like(like),
                Place.state.like(like),
                Place.address.like(like),
                Place.notes.like(like),
            )
        )
    if city:
        stmt = stmt.where(Place.city == city)
    if state:
        stmt = stmt.where(Place.state == state)
    if category_id:
        stmt = stmt.where(Place.category_id == category_id)
    if vlog_status == "featured":
        stmt = stmt.where(
            or_(
                Place.vlog_youtube_url.is_not(None),
                Place.vlog_tiktok_url.is_not(None),
                Place.vlog_instagram_url.is_not(None),
            )
        )
    elif vlog_status == "planned":
        stmt = stmt.where(
            Place.vlog_youtube_url.is_(None),
            Place.vlog_tiktok_url.is_(None),
            Place.vlog_instagram_url.is_(None),
        )

    places = db.execute(stmt).scalars().all()
    categories = db.execute(select(Category).order_by(Category.name.asc())).scalars().all()

    saved_place_ids: set[int] = set()
    user_id = session.get("user_id")
    if user_id is not None and not session.get("anonymous_preview"):
        saved_place_ids = set(
            db.execute(
                select(SavedPlace.place_id).where(SavedPlace.user_id == user_id)
            ).scalars().all()
        )

    return render_template(
        "public/index.html",
        places=places,
        categories=categories,
        q=q or "",
        city=city or "",
        state=state or "",
        category_id=category_id or "",
        vlog_status=vlog_status or "",
        sort=sort,
        saved_place_ids=saved_place_ids,
    )


@public_bp.route("/places/<int:place_id>")
@require_feature("places")
def place_detail(place_id: int) -> str:
    db = get_session(current_app)
    place = db.get(Place, place_id)
    if place is None:
        abort(404)

    is_saved = False
    user_id = session.get("user_id")
    if user_id is not None and not session.get("anonymous_preview"):
        is_saved = db.get(SavedPlace, (user_id, place_id)) is not None

    return render_template("public/detail.html", place=place, is_saved=is_saved)


@public_bp.route("/saved")
@login_required
def saved_places() -> str:
    db = get_session(current_app)
    user_id = int(session["user_id"])
    places = (
        db.execute(
            select(Place)
            .join(SavedPlace, SavedPlace.place_id == Place.id)
            .where(SavedPlace.user_id == user_id)
            .order_by(SavedPlace.created_at.desc(), Place.name.asc())
        )
        .scalars()
        .all()
    )
    return render_template("public/saved.html", places=places)


@public_bp.route("/places/<int:place_id>/save", methods=["POST"])
@login_required
def save_place(place_id: int):
    db = get_session(current_app)
    if db.get(Place, place_id) is None:
        abort(404)

    user_id = int(session["user_id"])
    if db.get(SavedPlace, (user_id, place_id)) is None:
        db.add(SavedPlace(user_id=user_id, place_id=place_id))
        db.commit()

    next_url = _safe_local_next(
        request.form.get("next"),
        url_for("public.place_detail", place_id=place_id),
    )
    return redirect(next_url)


@public_bp.route("/places/<int:place_id>/unsave", methods=["POST"])
@login_required
def unsave_place(place_id: int):
    db = get_session(current_app)
    user_id = int(session["user_id"])
    saved = db.get(SavedPlace, (user_id, place_id))
    if saved is not None:
        db.delete(saved)
        db.commit()

    next_url = _safe_local_next(request.form.get("next"), url_for("public.saved_places"))
    return redirect(next_url)


@public_bp.route("/blog")
@require_feature("blog")
def blog_index() -> str:
    db = get_session(current_app)
    posts = (
        db.execute(
            select(BlogPost)
            .where(
                BlogPost.status == "published",
                or_(BlogPost.publish_at.is_(None), BlogPost.publish_at <= text("datetime('now')")),
            )
            .order_by(text("COALESCE(publish_at, created_at) DESC"), BlogPost.id.desc())
            .limit(200)
        )
        .scalars()
        .all()
    )
    return render_template("public/blog_index.html", posts=posts)


@public_bp.route("/blog/<slug>")
@require_feature("blog")
def blog_post(slug: str) -> str:
    db = get_session(current_app)
    post = (
        db.execute(
            select(BlogPost)
            .where(
                BlogPost.slug == slug,
                BlogPost.status == "published",
                or_(BlogPost.publish_at.is_(None), BlogPost.publish_at <= text("datetime('now')")),
            )
            .limit(1)
        )
        .scalars()
        .first()
    )
    if post is None:
        abort(404)
    return render_template(
        "public/blog_post.html",
        post=post,
        post_html=render_markdown(post.content_md),
    )


@public_bp.route("/about")
@require_feature("about")
def about() -> str:
    return render_template("public/about.html")


@public_bp.route("/contact", methods=["GET", "POST"])
@require_feature("contact")
def contact() -> str:
    db = get_session(current_app)

    if request.method == "POST":
        name = clean_str(request.form.get("name"))
        email = clean_str(request.form.get("email"))
        subject = clean_str(request.form.get("subject"))
        message = clean_str(request.form.get("message"))
        honeypot = clean_str(request.form.get("website"))

        if honeypot:
            flash("Thanks!", "info")
            return redirect(url_for("public.contact"))

        if not name or not email or not subject or not message:
            flash("All fields are required", "error")
        else:
            cm = ContactMessage(name=name, email=email, subject=subject, message=message)
            db.add(cm)
            db.commit()
            try:
                send_contact_email_if_configured(
                    db=db,
                    name=name,
                    email=email,
                    subject=subject,
                    message=message,
                )
            except Exception:
                pass
            flash("Message received. We'll get back to you soon.", "info")
            return redirect(url_for("public.contact"))

    return render_template("public/contact.html")
