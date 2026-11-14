"""Filming planning workspace — standalone read-only blueprint.

Planning happens client-side in the MVP; no external services are called
without the user choosing to open a map search or route.
"""
from flask import Blueprint, current_app, jsonify, render_template, request, url_for
from sqlalchemy import func, select

from ..access_control import require_feature
from ..db import get_session
from ..models import Category, Place

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
