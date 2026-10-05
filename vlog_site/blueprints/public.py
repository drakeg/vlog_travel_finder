from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlencode

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask import send_from_directory
from sqlalchemy import case, func, or_, select, text

from ..access_control import require_feature
from ..db import get_session
from ..models import BlogPost, Category, ContactMessage, Place, SavedPlace, Trip, TripChecklistItem, TripPlace
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


def _clean_iso_date(value: str | None) -> str | None:
    cleaned = clean_str(value)
    if not cleaned:
        return None
    date.fromisoformat(cleaned)
    return cleaned


def _valid_trip_date_range(start_date: str | None, end_date: str | None) -> bool:
    return not (start_date and end_date and end_date < start_date)


def _clean_hhmm_time(value: str | None) -> str | None:
    cleaned = clean_str(value)
    if not cleaned:
        return None
    parsed = time.fromisoformat(cleaned)
    return parsed.strftime("%H:%M")


def _stop_date_within_trip(trip: Trip, planned_date: str | None) -> bool:
    if not planned_date:
        return True
    if trip.start_date and planned_date < trip.start_date:
        return False
    if trip.end_date and planned_date > trip.end_date:
        return False
    return True


def _ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\r", "\\n")
        .replace("\n", "\\n")
    )


def _place_address(place: Place) -> str:
    parts = [place.address, place.city, place.state, place.zipcode]
    return ", ".join(part.strip() for part in parts if part and part.strip())


def _maps_route_location(place: Place) -> str | None:
    if place.latitude is not None and place.longitude is not None:
        return f"{place.latitude},{place.longitude}"
    address = _place_address(place)
    return address or None


def _google_maps_route_url(stops: list[dict]) -> str | None:
    locations = [
        location
        for stop in stops
        if (location := _maps_route_location(stop["place"]))
    ]
    if len(locations) < 2:
        return None

    params = {
        "api": "1",
        "origin": locations[0],
        "destination": locations[-1],
        "travelmode": "driving",
    }
    if len(locations) > 2:
        params["waypoints"] = "|".join(locations[1:-1])
    return "https://www.google.com/maps/dir/?" + urlencode(params)


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

    # Apply filters before counting/paginating; always tie-break on the ID.
    stmt = select(Place)
    if sort == "name":
        ordering = (Place.name.asc(), text("COALESCE(state, '')"), text("COALESCE(city, '')"), Place.id.asc())
    elif sort == "newest":
        ordering = (Place.created_at.desc(), Place.id.desc())
    else:
        sort = "location"
        ordering = (text("COALESCE(state, '')"), text("COALESCE(city, '')"), Place.name.asc(), Place.id.asc())
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

    page_size = 24
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    page_count = max(1, (total + page_size - 1) // page_size)
    try:
        requested_page = int(request.args.get("page", "1"))
    except (ValueError, TypeError):
        requested_page = 1
    page = min(max(requested_page, 1), page_count)
    places = db.execute(
        stmt.order_by(*ordering).limit(page_size).offset((page - 1) * page_size)
    ).scalars().all()
    first_result = (page - 1) * page_size + 1 if total else 0
    last_result = min(page * page_size, total)
    categories = db.execute(select(Category).order_by(Category.name.asc())).scalars().all()

    saved_place_ids: set[int] = set()
    user_id = session.get("user_id")
    if user_id is not None and not session.get("anonymous_preview"):
        saved_place_ids = set(
            db.execute(
                select(SavedPlace.place_id).where(
                    SavedPlace.user_id == user_id,
                    SavedPlace.place_id.in_([place.id for place in places]),
                )
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
        page=page,
        page_count=page_count,
        total=total,
        first_result=first_result,
        last_result=last_result,
        page_args={
            "q": q or "", "city": city or "", "state": state or "",
            "category_id": category_id or "", "vlog_status": vlog_status or "",
            "sort": sort,
        },
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

    user_trips = []
    if user_id is not None and not session.get("anonymous_preview"):
        user_trips = (
            db.execute(
                select(Trip)
                .where(Trip.user_id == user_id)
                .order_by(Trip.created_at.desc(), Trip.id.desc())
            )
            .scalars()
            .all()
        )

    return render_template(
        "public/detail.html",
        place=place,
        is_saved=is_saved,
        user_trips=user_trips,
    )


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
    trips = (
        db.execute(
            select(Trip)
            .where(Trip.user_id == user_id)
            .order_by(Trip.created_at.desc(), Trip.id.desc())
        )
        .scalars()
        .all()
    )

    return render_template("public/saved.html", places=places, trips=trips)


@public_bp.route("/saved/add-to-trip", methods=["POST"])
@login_required
def saved_add_to_trip():
    db = get_session(current_app)
    user_id = int(session["user_id"])

    try:
        trip_id = int(request.form.get("trip_id", ""))
    except ValueError:
        abort(404)

    trip = (
        db.execute(
            select(Trip).where(Trip.id == trip_id, Trip.user_id == user_id)
        )
        .scalars()
        .first()
    )
    if trip is None:
        abort(404)

    selected_ids: list[int] = []
    for raw in request.form.getlist("place_ids"):
        try:
            place_id = int(raw)
        except ValueError:
            continue
        if place_id not in selected_ids:
            selected_ids.append(place_id)

    if not selected_ids:
        flash("Select at least one saved place", "error")
        return redirect(url_for("public.saved_places"))

    saved_ids = set(
        db.execute(
            select(SavedPlace.place_id).where(
                SavedPlace.user_id == user_id,
                SavedPlace.place_id.in_(selected_ids),
            )
        ).scalars().all()
    )

    existing_place_ids = set(
        db.execute(
            select(TripPlace.place_id).where(TripPlace.trip_id == trip.id)
        ).scalars().all()
    )
    positions = db.execute(
        select(TripPlace.position).where(TripPlace.trip_id == trip.id)
    ).scalars().all()
    next_position = max(positions, default=0) + 1

    added = 0
    for place_id in selected_ids:
        if place_id not in saved_ids or place_id in existing_place_ids:
            continue
        db.add(
            TripPlace(
                trip_id=trip.id,
                place_id=place_id,
                position=next_position,
            )
        )
        next_position += 1
        added += 1

    if added:
        db.commit()
        flash(f"Added {added} saved place{'s' if added != 1 else ''} to {trip.name}", "info")
    else:
        flash("No new saved places were added", "info")

    return redirect(url_for("public.saved_places"))


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


def _current_user_trip_or_404(db, trip_id: int) -> Trip:
    user_id = int(session["user_id"])
    trip = (
        db.execute(
            select(Trip).where(Trip.id == trip_id, Trip.user_id == user_id)
        )
        .scalars()
        .first()
    )
    if trip is None:
        abort(404)
    return trip


def _trip_itinerary_data(db, trip: Trip) -> tuple[list[dict], list[dict], list[dict]]:
    rows = db.execute(
        select(Place, TripPlace)
        .join(TripPlace, TripPlace.place_id == Place.id)
        .where(TripPlace.trip_id == trip.id)
        .order_by(
            TripPlace.position.asc(),
            TripPlace.created_at.asc(),
            Place.name.asc(),
        )
    ).all()

    stops = [
        {
            "place": place,
            "position": trip_place.position,
            "notes": trip_place.notes,
            "planned_date": trip_place.planned_date,
            "planned_time": trip_place.planned_time,
            "sequence": index,
        }
        for index, (place, trip_place) in enumerate(rows, start=1)
    ]

    scheduled_by_date: dict[str, list[dict]] = {}
    unscheduled_stops: list[dict] = []
    for stop in stops:
        planned_date = stop["planned_date"]
        if planned_date:
            scheduled_by_date.setdefault(planned_date, []).append(stop)
        else:
            unscheduled_stops.append(stop)

    day_groups = [
        {
            "date": planned_date,
            "stops": scheduled_by_date[planned_date],
            "route_url": _google_maps_route_url(scheduled_by_date[planned_date]),
        }
        for planned_date in sorted(scheduled_by_date)
    ]
    return stops, day_groups, unscheduled_stops


@public_bp.route("/trips", methods=["GET", "POST"])
@login_required
def trips() -> str:
    db = get_session(current_app)
    user_id = int(session["user_id"])

    if request.method == "POST":
        name = clean_str(request.form.get("name"))
        try:
            start_date = _clean_iso_date(request.form.get("start_date"))
            end_date = _clean_iso_date(request.form.get("end_date"))
        except ValueError:
            start_date = end_date = None
            flash("Trip dates must use a valid YYYY-MM-DD date", "error")
        else:
            if not name:
                flash("Trip name is required", "error")
            elif not _valid_trip_date_range(start_date, end_date):
                flash("Trip end date cannot be earlier than the start date", "error")
            else:
                db.add(
                    Trip(
                        user_id=user_id,
                        name=name,
                        notes=clean_str(request.form.get("notes")),
                        start_date=start_date,
                        end_date=end_date,
                    )
                )
                db.commit()
                flash("Trip created", "info")
                return redirect(url_for("public.trips"))

    trips = (
        db.execute(
            select(Trip)
            .where(Trip.user_id == user_id)
            .order_by(Trip.created_at.desc(), Trip.id.desc())
        )
        .scalars()
        .all()
    )

    visibility = clean_str(request.args.get("visibility")) or "active"
    if visibility not in {"active", "archived", "all"}:
        visibility = "active"
    if visibility == "active":
        trips = [trip for trip in trips if not trip.archived]
    elif visibility == "archived":
        trips = [trip for trip in trips if trip.archived]

    counts = dict(
        db.execute(
            select(TripPlace.trip_id, text("COUNT(1)"))
            .join(Trip, Trip.id == TripPlace.trip_id)
            .where(Trip.user_id == user_id)
            .group_by(TripPlace.trip_id)
        ).all()
    )

    today = date.today().isoformat()
    checklist_stats = {
        trip_id: {
            "total": int(total or 0),
            "completed": int(completed or 0),
            "overdue": int(overdue or 0),
        }
        for trip_id, total, completed, overdue in db.execute(
            select(
                TripChecklistItem.trip_id,
                func.count(TripChecklistItem.id),
                func.sum(
                    case(
                        (TripChecklistItem.completed.is_(True), 1),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (
                            TripChecklistItem.completed.is_(False)
                            & TripChecklistItem.due_date.is_not(None)
                            & (TripChecklistItem.due_date < today),
                            1,
                        ),
                        else_=0,
                    )
                ),
            )
            .join(Trip, Trip.id == TripChecklistItem.trip_id)
            .where(Trip.user_id == user_id)
            .group_by(TripChecklistItem.trip_id)
        ).all()
    }
    prep_filter = clean_str(request.args.get("prep")) or "all"
    valid_prep_filters = {"all", "overdue", "incomplete", "complete", "none"}
    if prep_filter not in valid_prep_filters:
        prep_filter = "all"

    if prep_filter != "all":
        filtered_trips = []
        for trip in trips:
            stats = checklist_stats.get(trip.id)
            if prep_filter == "none":
                matches = stats is None
            elif stats is None:
                matches = False
            elif prep_filter == "overdue":
                matches = stats["overdue"] > 0
            elif prep_filter == "incomplete":
                matches = stats["completed"] < stats["total"]
            else:
                matches = stats["total"] > 0 and stats["completed"] == stats["total"]
            if matches:
                filtered_trips.append(trip)
        trips = filtered_trips

    trip_search = clean_str(request.args.get("q")) or ""
    if trip_search:
        needle = trip_search.casefold()
        trips = [
            trip
            for trip in trips
            if needle in trip.name.casefold()
            or (trip.notes and needle in trip.notes.casefold())
        ]

    date_filter = clean_str(request.args.get("date")) or "all"
    valid_date_filters = {"all", "upcoming", "active", "past", "undated"}
    if date_filter not in valid_date_filters:
        date_filter = "all"

    if date_filter != "all":
        date_filtered_trips = []
        for trip in trips:
            if not trip.start_date and not trip.end_date:
                state = "undated"
            elif trip.end_date and trip.end_date < today:
                state = "past"
            elif trip.start_date and trip.start_date > today:
                state = "upcoming"
            else:
                state = "active"

            if state == date_filter:
                date_filtered_trips.append(trip)
        trips = date_filtered_trips

    trip_sort = clean_str(request.args.get("sort")) or "newest"
    valid_trip_sorts = {"newest", "oldest", "start", "name_asc", "name_desc", "prep"}
    if trip_sort not in valid_trip_sorts:
        trip_sort = "newest"

    if trip_sort == "oldest":
        trips = list(reversed(trips))
    elif trip_sort == "start":
        trips = sorted(
            trips,
            key=lambda trip: (trip.start_date is None, trip.start_date or ""),
        )
    elif trip_sort == "name_asc":
        trips = sorted(trips, key=lambda trip: trip.name.casefold())
    elif trip_sort == "name_desc":
        trips = sorted(trips, key=lambda trip: trip.name.casefold(), reverse=True)
    elif trip_sort == "prep":
        def prep_rank(trip):
            stats = checklist_stats.get(trip.id)
            if stats is None:
                return 3
            if stats["overdue"] > 0:
                return 0
            if stats["completed"] < stats["total"]:
                return 1
            return 2

        trips = sorted(trips, key=prep_rank)

    page_size = 24
    total_trips = len(trips)
    total_pages = max(1, (total_trips + page_size - 1) // page_size)
    try:
        trip_page = int(request.args.get("page", "1"))
    except ValueError:
        trip_page = 1
    trip_page = max(1, min(trip_page, total_pages))
    page_start = (trip_page - 1) * page_size
    trips = trips[page_start : page_start + page_size]

    return render_template(
        "public/trips.html",
        trips=trips,
        trip_counts=counts,
        checklist_stats=checklist_stats,
        prep_filter=prep_filter,
        trip_search=trip_search,
        date_filter=date_filter,
        trip_sort=trip_sort,
        visibility=visibility,
        trip_page=trip_page,
        total_pages=total_pages,
        total_trips=total_trips,
    )


@public_bp.route("/trips/<int:trip_id>")
@login_required
def trip_detail(trip_id: int) -> str:
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    stops, day_groups, unscheduled_stops = _trip_itinerary_data(db, trip)
    checklist_items = (
        db.execute(
            select(TripChecklistItem)
            .where(TripChecklistItem.trip_id == trip.id)
            .order_by(
                TripChecklistItem.created_at.asc(),
                TripChecklistItem.id.asc(),
            )
        )
        .scalars()
        .all()
    )
    checklist_completed = sum(1 for item in checklist_items if item.completed)
    user_id = int(session["user_id"])
    other_trips = (
        db.execute(
            select(Trip)
            .where(Trip.user_id == user_id, Trip.id != trip.id)
            .order_by(Trip.created_at.desc(), Trip.id.desc())
        )
        .scalars()
        .all()
    )

    return render_template(
        "public/trip_detail.html",
        trip=trip,
        stops=stops,
        day_groups=day_groups,
        unscheduled_stops=unscheduled_stops,
        other_trips=other_trips,
        checklist_items=checklist_items,
        checklist_completed=checklist_completed,
        checklist_remaining=len(checklist_items) - checklist_completed,
        today_iso=date.today().isoformat(),
    )


@public_bp.route("/trips/<int:trip_id>/checklist", methods=["POST"])
@login_required
def trip_checklist_add(trip_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    item_text = clean_str(request.form.get("text"))
    try:
        due_date = _clean_iso_date(request.form.get("due_date"))
    except ValueError:
        flash("Checklist due date must be a valid date", "error")
        return redirect(url_for("public.trip_detail", trip_id=trip.id))

    if not item_text:
        flash("Checklist item is required", "error")
    else:
        db.add(
            TripChecklistItem(
                trip_id=trip.id,
                text=item_text,
                due_date=due_date,
            )
        )
        db.commit()
        flash("Checklist item added", "info")
    return redirect(url_for("public.trip_detail", trip_id=trip.id))


@public_bp.route("/trips/<int:trip_id>/checklist/import", methods=["POST"])
@login_required
def trip_checklist_import(trip_id: int):
    db = get_session(current_app)
    target_trip = _current_user_trip_or_404(db, trip_id)

    try:
        source_trip_id = int(request.form.get("source_trip_id", ""))
    except ValueError:
        abort(404)

    source_trip = (
        db.execute(
            select(Trip).where(
                Trip.id == source_trip_id,
                Trip.user_id == int(session["user_id"]),
            )
        )
        .scalars()
        .first()
    )
    if source_trip is None or source_trip.id == target_trip.id:
        abort(404)

    source_items = (
        db.execute(
            select(TripChecklistItem)
            .where(TripChecklistItem.trip_id == source_trip.id)
            .order_by(
                TripChecklistItem.created_at.asc(),
                TripChecklistItem.id.asc(),
            )
        )
        .scalars()
        .all()
    )

    existing_text = {
        item_text.casefold()
        for item_text in db.execute(
            select(TripChecklistItem.text).where(
                TripChecklistItem.trip_id == target_trip.id
            )
        ).scalars().all()
    }

    imported = 0
    for item in source_items:
        normalized = item.text.casefold()
        if normalized in existing_text:
            continue
        db.add(
            TripChecklistItem(
                trip_id=target_trip.id,
                text=item.text,
                completed=False,
            )
        )
        existing_text.add(normalized)
        imported += 1

    if imported:
        db.commit()
        flash(
            f"Imported {imported} checklist item{'s' if imported != 1 else ''}",
            "info",
        )
    else:
        flash("No new checklist items to import", "info")

    return redirect(url_for("public.trip_detail", trip_id=target_trip.id))


@public_bp.route(
    "/trips/<int:trip_id>/checklist/<int:item_id>/due-date",
    methods=["POST"],
)
@login_required
def trip_checklist_due_date(trip_id: int, item_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    item = (
        db.execute(
            select(TripChecklistItem).where(
                TripChecklistItem.id == item_id,
                TripChecklistItem.trip_id == trip.id,
            )
        )
        .scalars()
        .first()
    )
    if item is None:
        abort(404)

    try:
        due_date = _clean_iso_date(request.form.get("due_date"))
    except ValueError:
        flash("Checklist due date must be a valid date", "error")
        return redirect(url_for("public.trip_detail", trip_id=trip.id))

    item.due_date = due_date
    db.commit()
    flash("Checklist due date updated", "info")
    return redirect(url_for("public.trip_detail", trip_id=trip.id))


@public_bp.route(
    "/trips/<int:trip_id>/checklist/<int:item_id>/toggle",
    methods=["POST"],
)
@login_required
def trip_checklist_toggle(trip_id: int, item_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    item = (
        db.execute(
            select(TripChecklistItem).where(
                TripChecklistItem.id == item_id,
                TripChecklistItem.trip_id == trip.id,
            )
        )
        .scalars()
        .first()
    )
    if item is None:
        abort(404)
    item.completed = not item.completed
    db.commit()
    flash("Checklist updated", "info")
    return redirect(url_for("public.trip_detail", trip_id=trip.id))


@public_bp.route(
    "/trips/<int:trip_id>/checklist/<int:item_id>/delete",
    methods=["POST"],
)
@login_required
def trip_checklist_delete(trip_id: int, item_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    item = (
        db.execute(
            select(TripChecklistItem).where(
                TripChecklistItem.id == item_id,
                TripChecklistItem.trip_id == trip.id,
            )
        )
        .scalars()
        .first()
    )
    if item is None:
        abort(404)
    db.delete(item)
    db.commit()
    flash("Checklist item deleted", "info")
    return redirect(url_for("public.trip_detail", trip_id=trip.id))


@public_bp.route("/trips/<int:trip_id>/print")
@login_required
def trip_print(trip_id: int) -> str:
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    stops, day_groups, unscheduled_stops = _trip_itinerary_data(db, trip)
    return render_template(
        "public/trip_print.html",
        trip=trip,
        stops=stops,
        day_groups=day_groups,
        unscheduled_stops=unscheduled_stops,
    )


@public_bp.route("/trips/<int:trip_id>/itinerary.txt")
@login_required
def trip_text_export(trip_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    stops, day_groups, unscheduled_stops = _trip_itinerary_data(db, trip)

    lines = [trip.name]
    if trip.start_date or trip.end_date:
        lines.append(
            f"Dates: {trip.start_date or 'TBD'} - {trip.end_date or 'TBD'}"
        )
    if trip.notes:
        lines.extend(["", f"Trip notes: {trip.notes}"])

    def add_stop(stop: dict) -> None:
        place = stop["place"]
        when = ""
        if stop["planned_time"]:
            when = f" @ {stop['planned_time']}"
        lines.append(f"{stop['sequence']}. {place.name}{when}")
        address_parts = [
            place.address,
            place.city,
            place.state,
            place.zipcode,
        ]
        address = ", ".join(
            part.strip() for part in address_parts if part and part.strip()
        )
        if address:
            lines.append(f"   Address: {address}")
        if stop["notes"]:
            lines.append(f"   Notes: {stop['notes']}")
        if place.google_maps_url:
            lines.append(f"   Maps: {place.google_maps_url}")

    for day in day_groups:
        lines.extend(["", day["date"]])
        for stop in day["stops"]:
            add_stop(stop)

    if unscheduled_stops:
        lines.extend(["", "Unscheduled"])
        for stop in unscheduled_stops:
            add_stop(stop)

    if not stops:
        lines.extend(["", "No itinerary stops yet."])

    content = "\n".join(lines) + "\n"
    response = current_app.response_class(content, mimetype="text/plain")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="trip-{trip.id}-itinerary.txt"'
    )
    return response


@public_bp.route("/trips/<int:trip_id>/itinerary.ics")
@login_required
def trip_calendar_export(trip_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    stops, _, _ = _trip_itinerary_data(db, trip)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Vlog Travel Finder//Trip Itinerary//EN",
        "CALSCALE:GREGORIAN",
    ]
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for stop in stops:
        planned_date = stop["planned_date"]
        if not planned_date:
            continue

        place = stop["place"]
        date_value = planned_date.replace("-", "")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:trip-{trip.id}-place-{place.id}@vlog-travel-finder",
                f"DTSTAMP:{dtstamp}",
            ]
        )

        if stop["planned_time"]:
            time_value = stop["planned_time"].replace(":", "")
            lines.append(f"DTSTART:{date_value}T{time_value}00")
        else:
            lines.append(f"DTSTART;VALUE=DATE:{date_value}")

        lines.append(f"SUMMARY:{_ics_escape(place.name)}")

        address = _place_address(place)
        if address:
            lines.append(f"LOCATION:{_ics_escape(address)}")

        description_parts = []
        if stop["notes"]:
            description_parts.append(stop["notes"])
        if place.google_maps_url:
            description_parts.append(f"Maps: {place.google_maps_url}")
        if description_parts:
            lines.append(
                "DESCRIPTION:" + _ics_escape("\n".join(description_parts))
            )

        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    content = "\r\n".join(lines) + "\r\n"
    response = current_app.response_class(
        content,
        mimetype="text/calendar",
    )
    response.headers["Content-Disposition"] = (
        f'attachment; filename="trip-{trip.id}-itinerary.ics"'
    )
    return response


@public_bp.route("/trips/<int:trip_id>/update", methods=["POST"])
@login_required
def trip_update(trip_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)

    name = clean_str(request.form.get("name"))
    try:
        start_date = _clean_iso_date(request.form.get("start_date"))
        end_date = _clean_iso_date(request.form.get("end_date"))
    except ValueError:
        flash("Trip dates must use a valid YYYY-MM-DD date", "error")
    else:
        if not name:
            flash("Trip name is required", "error")
        elif not _valid_trip_date_range(start_date, end_date):
            flash("Trip end date cannot be earlier than the start date", "error")
        else:
            trip.name = name
            trip.notes = clean_str(request.form.get("notes"))
            trip.start_date = start_date
            trip.end_date = end_date
            db.commit()
            flash("Trip details saved", "info")

    return redirect(url_for("public.trip_detail", trip_id=trip.id))


@public_bp.route("/trips/<int:trip_id>/duplicate", methods=["POST"])
@login_required
def trip_duplicate(trip_id: int):
    db = get_session(current_app)
    source = _current_user_trip_or_404(db, trip_id)
    user_id = int(session["user_id"])

    requested_start_raw = clean_str(request.form.get("new_start_date"))
    date_delta = timedelta(0)
    duplicate_start_date = source.start_date
    duplicate_end_date = source.end_date

    if requested_start_raw:
        if not source.start_date:
            flash("Set a start date on the source trip before shifting dates", "error")
            return redirect(url_for("public.trip_detail", trip_id=source.id))
        try:
            requested_start = _clean_iso_date(requested_start_raw)
            source_start = date.fromisoformat(source.start_date)
        except ValueError:
            flash("Enter a valid new start date", "error")
            return redirect(url_for("public.trip_detail", trip_id=source.id))

        assert requested_start is not None
        date_delta = date.fromisoformat(requested_start) - source_start
        duplicate_start_date = requested_start
        if source.end_date:
            duplicate_end_date = (
                date.fromisoformat(source.end_date) + date_delta
            ).isoformat()

    duplicate = Trip(
        user_id=user_id,
        name=f"{source.name} (Copy)",
        notes=source.notes,
        start_date=duplicate_start_date,
        end_date=duplicate_end_date,
        archived=False,
    )
    db.add(duplicate)
    db.flush()

    source_stops = (
        db.execute(
            select(TripPlace)
            .where(TripPlace.trip_id == source.id)
            .order_by(
                TripPlace.position.asc(),
                TripPlace.created_at.asc(),
                TripPlace.place_id.asc(),
            )
        )
        .scalars()
        .all()
    )
    for stop in source_stops:
        db.add(
            TripPlace(
                trip_id=duplicate.id,
                place_id=stop.place_id,
                position=stop.position,
                notes=stop.notes,
                planned_date=(
                    (date.fromisoformat(stop.planned_date) + date_delta).isoformat()
                    if stop.planned_date and requested_start_raw
                    else stop.planned_date
                ),
                planned_time=stop.planned_time,
            )
        )

    source_checklist = (
        db.execute(
            select(TripChecklistItem)
            .where(TripChecklistItem.trip_id == source.id)
            .order_by(
                TripChecklistItem.created_at.asc(),
                TripChecklistItem.id.asc(),
            )
        )
        .scalars()
        .all()
    )
    for item in source_checklist:
        db.add(
            TripChecklistItem(
                trip_id=duplicate.id,
                text=item.text,
                completed=False,
            )
        )

    db.commit()
    flash("Trip duplicated", "info")
    return redirect(url_for("public.trip_detail", trip_id=duplicate.id))


@public_bp.route("/trips/<int:trip_id>/archive", methods=["POST"])
@login_required
def trip_archive(trip_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    trip.archived = True
    db.commit()
    flash("Trip archived", "info")
    return redirect(url_for("public.trips", visibility="archived"))


@public_bp.route("/trips/<int:trip_id>/restore", methods=["POST"])
@login_required
def trip_restore(trip_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    trip.archived = False
    db.commit()
    flash("Trip restored", "info")
    return redirect(url_for("public.trips"))


@public_bp.route("/trips/<int:trip_id>/delete", methods=["POST"])
@login_required
def trip_delete(trip_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    db.delete(trip)
    db.commit()
    flash("Trip deleted", "info")
    return redirect(url_for("public.trips"))


@public_bp.route("/trips/<int:trip_id>/places/<int:place_id>/add", methods=["POST"])
@login_required
def trip_add_place(trip_id: int, place_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    if db.get(Place, place_id) is None:
        abort(404)

    if db.get(TripPlace, (trip.id, place_id)) is None:
        positions = db.execute(
            select(TripPlace.position).where(TripPlace.trip_id == trip.id)
        ).scalars().all()
        next_position = max(positions, default=0) + 1
        db.add(
            TripPlace(
                trip_id=trip.id,
                place_id=place_id,
                position=next_position,
            )
        )
        db.commit()

    next_url = _safe_local_next(
        request.form.get("next"),
        url_for("public.trip_detail", trip_id=trip.id),
    )
    return redirect(next_url)


@public_bp.route(
    "/trips/<int:trip_id>/places/<int:place_id>/move/<direction>",
    methods=["POST"],
)
@login_required
def trip_move_place(trip_id: int, place_id: int, direction: str):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    if direction not in {"up", "down"}:
        abort(404)

    rows = (
        db.execute(
            select(TripPlace)
            .where(TripPlace.trip_id == trip.id)
            .order_by(
                TripPlace.position.asc(),
                TripPlace.created_at.asc(),
                TripPlace.place_id.asc(),
            )
        )
        .scalars()
        .all()
    )

    current_index = next(
        (index for index, row in enumerate(rows) if row.place_id == place_id),
        None,
    )
    if current_index is None:
        abort(404)

    target_index = current_index - 1 if direction == "up" else current_index + 1
    if 0 <= target_index < len(rows):
        current = rows[current_index]
        target = rows[target_index]
        current.position, target.position = target.position, current.position
        db.commit()

    return redirect(url_for("public.trip_detail", trip_id=trip.id))


@public_bp.route("/trips/<int:trip_id>/schedule-bulk", methods=["POST"])
@login_required
def trip_bulk_schedule(trip_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)

    selected_ids: list[int] = []
    for raw in request.form.getlist("place_ids"):
        try:
            place_id = int(raw)
        except ValueError:
            continue
        if place_id not in selected_ids:
            selected_ids.append(place_id)

    if not selected_ids:
        flash("Select at least one stop", "error")
        return redirect(url_for("public.trip_detail", trip_id=trip.id))

    rows = (
        db.execute(
            select(TripPlace)
            .where(
                TripPlace.trip_id == trip.id,
                TripPlace.place_id.in_(selected_ids),
            )
            .order_by(
                TripPlace.position.asc(),
                TripPlace.created_at.asc(),
                TripPlace.place_id.asc(),
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        flash("No selected stops belong to this trip", "error")
        return redirect(url_for("public.trip_detail", trip_id=trip.id))

    action = clean_str(request.form.get("action")) or "date"
    if action == "copy":
        try:
            target_trip_id = int(request.form.get("target_trip_id", ""))
        except ValueError:
            abort(404)

        target_trip = (
            db.execute(
                select(Trip).where(
                    Trip.id == target_trip_id,
                    Trip.user_id == int(session["user_id"]),
                )
            )
            .scalars()
            .first()
        )
        if target_trip is None or target_trip.id == trip.id:
            abort(404)

        existing_place_ids = set(
            db.execute(
                select(TripPlace.place_id).where(TripPlace.trip_id == target_trip.id)
            ).scalars().all()
        )
        target_positions = db.execute(
            select(TripPlace.position).where(TripPlace.trip_id == target_trip.id)
        ).scalars().all()
        next_position = max(target_positions, default=0) + 1

        copied = 0
        for row in rows:
            if row.place_id in existing_place_ids:
                continue
            planned_date = (
                row.planned_date
                if _stop_date_within_trip(target_trip, row.planned_date)
                else None
            )
            db.add(
                TripPlace(
                    trip_id=target_trip.id,
                    place_id=row.place_id,
                    position=next_position,
                    notes=row.notes,
                    planned_date=planned_date,
                    planned_time=row.planned_time,
                )
            )
            existing_place_ids.add(row.place_id)
            next_position += 1
            copied += 1

        if copied:
            db.commit()
            flash(
                f"Copied {copied} stop{'s' if copied != 1 else ''} to {target_trip.name}",
                "info",
            )
        else:
            flash("No new stops were copied", "info")
        return redirect(url_for("public.trip_detail", trip_id=trip.id))

    if action == "times":
        try:
            start_time = _clean_hhmm_time(request.form.get("start_time"))
            interval_minutes = int(request.form.get("interval_minutes", ""))
        except (TypeError, ValueError):
            flash("Enter a valid start time and interval", "error")
            return redirect(url_for("public.trip_detail", trip_id=trip.id))

        if start_time is None or not 5 <= interval_minutes <= 720:
            flash("Interval must be between 5 and 720 minutes", "error")
            return redirect(url_for("public.trip_detail", trip_id=trip.id))

        parsed_start = time.fromisoformat(start_time)
        start_minutes = parsed_start.hour * 60 + parsed_start.minute
        generated_minutes = [
            start_minutes + index * interval_minutes
            for index in range(len(rows))
        ]
        if generated_minutes[-1] >= 24 * 60:
            flash("Sequential times cannot roll into the next day", "error")
            return redirect(url_for("public.trip_detail", trip_id=trip.id))

        for row, minute_value in zip(rows, generated_minutes):
            hour, minute = divmod(minute_value, 60)
            row.planned_time = f"{hour:02d}:{minute:02d}"
        db.commit()
        flash(
            f"Scheduled times for {len(rows)} stop{'s' if len(rows) != 1 else ''}",
            "info",
        )
        return redirect(url_for("public.trip_detail", trip_id=trip.id))

    if action != "date":
        abort(400)

    try:
        planned_date = _clean_iso_date(request.form.get("planned_date"))
    except ValueError:
        flash("Bulk stop date must use a valid date", "error")
        return redirect(url_for("public.trip_detail", trip_id=trip.id))

    if not _stop_date_within_trip(trip, planned_date):
        flash("Stop date must fall within the trip date range", "error")
        return redirect(url_for("public.trip_detail", trip_id=trip.id))

    for row in rows:
        row.planned_date = planned_date
    db.commit()

    date_action = "Cleared dates from" if planned_date is None else "Scheduled"
    flash(
        f"{date_action} {len(rows)} stop{'s' if len(rows) != 1 else ''}",
        "info",
    )
    return redirect(url_for("public.trip_detail", trip_id=trip.id))


@public_bp.route("/trips/<int:trip_id>/places/<int:place_id>/schedule", methods=["POST"])
@login_required
def trip_update_place_schedule(trip_id: int, place_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    row = db.get(TripPlace, (trip.id, place_id))
    if row is None:
        abort(404)

    try:
        planned_date = _clean_iso_date(request.form.get("planned_date"))
        planned_time = _clean_hhmm_time(request.form.get("planned_time"))
    except ValueError:
        flash("Stop schedule must use a valid date and time", "error")
    else:
        if not _stop_date_within_trip(trip, planned_date):
            flash("Stop date must fall within the trip date range", "error")
        else:
            row.planned_date = planned_date
            row.planned_time = planned_time
            db.commit()
            flash("Stop schedule saved", "info")

    return redirect(url_for("public.trip_detail", trip_id=trip.id))


@public_bp.route("/trips/<int:trip_id>/places/<int:place_id>/notes", methods=["POST"])
@login_required
def trip_update_place_notes(trip_id: int, place_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    row = db.get(TripPlace, (trip.id, place_id))
    if row is None:
        abort(404)

    row.notes = clean_str(request.form.get("notes"))
    db.commit()
    flash("Stop notes saved", "info")
    return redirect(url_for("public.trip_detail", trip_id=trip.id))


@public_bp.route("/trips/<int:trip_id>/places/<int:place_id>/remove", methods=["POST"])
@login_required
def trip_remove_place(trip_id: int, place_id: int):
    db = get_session(current_app)
    trip = _current_user_trip_or_404(db, trip_id)
    row = db.get(TripPlace, (trip.id, place_id))
    if row is not None:
        db.delete(row)
        db.commit()

    return redirect(url_for("public.trip_detail", trip_id=trip.id))


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
