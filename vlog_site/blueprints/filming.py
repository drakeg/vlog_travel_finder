"""Filming Planner routes integrated into the Vlog Travel Finder application."""
from flask import Blueprint, current_app, jsonify, render_template, request, session, url_for
from sqlalchemy import func, select

from ..access_control import require_feature
from ..db import get_session
from ..models import Category, Place
from ..services.filming_places import OSMDiscoveryUnavailable, discover_osm_places

filming_bp = Blueprint("filming", __name__)


@filming_bp.get("/filming-planner")
def index():
    return render_template("public/filming_planner.html")


def _discovery_city(location: str) -> str:
    """Use an explicitly entered city or the city in a comma-separated address."""
    parts = [part.strip() for part in location.split(",") if part.strip()]
    if len(parts) >= 3:
        return parts[-2]
    return parts[0] if parts else ""


def _filming_rationale(category: str | None) -> str:
    """Suggest a content angle without claiming unverified venue details."""
    kind = (category or "local destination").lower()
    if "waterfall" in kind or "scenic" in kind or "park" in kind:
        return "Consider scenic establishing shots, environmental B-roll and a short location introduction; verify trail access and conditions."
    if "museum" in kind or "histor" in kind:
        return "Consider a history-focused introduction, exterior B-roll and a story about the destination; check filming permissions."
    if "food" in kind or "restaurant" in kind or "market" in kind:
        return "Consider a local food or market story, signage and detail shots; confirm business hours and filming permission."
    return "Consider an arrival sequence, distinctive details and an on-camera introduction; verify access and filming suitability."


@filming_bp.get("/filming-planner/discover")
@require_feature("places")
def discover():
    """Find existing catalog destinations in the requested city, not live POIs."""
    location = request.args.get("location", "").strip()
    if not 2 <= len(location) <= 120:
        return jsonify({"error": "Enter a city or location (2–120 characters).", "suggestions": []}), 400
    city = _discovery_city(location)
    if not 2 <= len(city) <= 80:
        return jsonify({"error": "Enter a valid city for catalog discovery.", "suggestions": []}), 400
    db = get_session(current_app)
    records = db.execute(
        select(Place, Category.name)
        .outerjoin(Category, Category.id == Place.category_id)
        .where(func.lower(Place.city) == city.lower())
        .order_by(Place.name.asc(), Place.id.asc())
        .limit(12)
    ).all()
    suggestions = [
        {
            "id": place.id,
            "name": place.name,
            "category": category or "Uncategorized",
            "city": place.city,
            "state": place.state,
            "place_url": url_for("public.place_detail", place_id=place.id),
            "why_film": _filming_rationale(category),
            "source": "Vlog Travel Finder catalog",
        }
        for place, category in records
    ]
    return jsonify({
        "city": city,
        "suggestions": suggestions,
        "source": "Vlog Travel Finder catalog",
        "limitations": "Not a live nearby search; driving time, access, weather and hours are unverified.",
    })


@filming_bp.get("/filming-planner/discover/nearby")
@require_feature("places")
def discover_nearby():
    """Opt-in coordinate search; never contact a remote service by default."""
    if session.get("user_id") is None or session.get("anonymous_preview"):
        return jsonify({"error": "Sign in to search external nearby destinations.", "suggestions": []}), 401
    if not current_app.config.get("FILMING_LIVE_DISCOVERY_ENABLED"):
        return jsonify({"error": "External nearby discovery is disabled on this deployment.", "suggestions": []}), 503
    try:
        places = discover_osm_places(
            request.args.get("latitude", ""),
            request.args.get("longitude", ""),
            radius_m=int(request.args.get("radius_m", "15000")),
            endpoint=current_app.config.get("FILMING_OVERPASS_URL", ""),
            user_agent=current_app.config.get("FILMING_OSM_USER_AGENT", ""),
        )
    except (ValueError, TypeError, OverflowError):
        return jsonify({"error": "Enter valid latitude, longitude and search radius.", "suggestions": []}), 400
    except OSMDiscoveryUnavailable:
        return jsonify({"error": "Nearby discovery is unavailable. Try catalog search or manual stops.", "suggestions": []}), 503
    return jsonify({
        "source": "OpenStreetMap contributors",
        "suggestions": places,
        "limitations": "Distances are straight-line estimates; hours, access, weather and actual driving times are unverified.",
    })


@filming_bp.get("/filming-planner/resolve-location")
@require_feature("places")
def resolve_location():
    """Resolve exact named catalog places without external geocoding or guessing."""
    if session.get("user_id") is None or session.get("anonymous_preview"):
        return jsonify({"error": "Sign in to resolve saved destinations.", "matches": []}), 401
    query = request.args.get("location", "").strip()
    if not 2 <= len(query) <= 120:
        return jsonify({"error": "Enter a saved destination name (2–120 characters).", "matches": []}), 400
    db = get_session(current_app)
    records = db.execute(
        select(Place)
        .where(func.lower(Place.name) == query.lower())
        .order_by(Place.id.asc())
        .limit(8)
    ).scalars().all()
    matches = [
        {
            "id": place.id,
            "name": place.name,
            "city": place.city,
            "state": place.state,
            "latitude": place.latitude,
            "longitude": place.longitude,
            "source": "Vlog Travel Finder catalog",
        }
        for place in records
        if place.latitude is not None and place.longitude is not None
    ]
    return jsonify({
        "matches": matches,
        "limitations": "Exact named saved destinations only. Verify the selected place before nearby search.",
    })
