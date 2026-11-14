"""Filming planning workspace — standalone read-only blueprint.

Planning happens client-side in the MVP; no external services are called
without the user choosing to open a map search or route.
"""
from flask import Blueprint, render_template

filming_bp = Blueprint("filming", __name__)


@filming_bp.get("/filming-planner")
def index():
    return render_template("public/filming_planner.html")
