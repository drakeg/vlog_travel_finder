from __future__ import annotations

import os

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask import send_from_directory
from sqlalchemy import or_, select, text

from ..access_control import require_feature
from ..db import get_session
from ..models import BlogPost, Category, ContactMessage, Place
from ..services.mail_service import send_contact_email_if_configured
from ..services.markdown_service import render_markdown
from ..services.settings_service import get_setting
from ..services.youtube_service import get_channel_url, get_latest_video, normalize_featured_embed_url
from ..utils import clean_str


public_bp = Blueprint("public", __name__)


@public_bp.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    upload_dir = os.path.join(current_app.instance_path, "uploads")
    return send_from_directory(upload_dir, filename)


@public_bp.route("/")
@require_feature("home")
def home() -> str:
    db = get_session(current_app)
    featured_youtube_url = normalize_featured_embed_url(get_setting(db, "featured_youtube_url"))
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
    try:
        category_id = int(category_id_raw) if category_id_raw else None
    except ValueError:
        category_id = None

    stmt = select(Place).order_by(text("COALESCE(state, ''), COALESCE(city, ''), name")).limit(200)
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

    places = db.execute(stmt).scalars().all()
    categories = db.execute(select(Category).order_by(Category.name.asc())).scalars().all()

    return render_template(
        "public/index.html",
        places=places,
        categories=categories,
        q=q or "",
        city=city or "",
        state=state or "",
        category_id=category_id or "",
    )


@public_bp.route("/places/<int:place_id>")
@require_feature("places")
def place_detail(place_id: int) -> str:
    db = get_session(current_app)
    place = db.get(Place, place_id)
    if place is None:
        abort(404)
    return render_template("public/detail.html", place=place)


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
