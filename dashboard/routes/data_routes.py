"""
Standalone online-data helper routes.
"""

import os
import sys
import traceback

from flask import Blueprint, jsonify, render_template, request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from utils.pakistan_data import PakistanDataConnector


data_bp = Blueprint("data", __name__)


@data_bp.route("/pakistan-data")
def pakistan_data_page():
    """Render the Pakistan online-data helper page."""
    return render_template("pakistan_data.html")


@data_bp.route("/api/data/pakistan/sources")
def pakistan_sources():
    """List supported Pakistan online data sources."""
    try:
        payload = PakistanDataConnector().source_catalog()
        return jsonify({"status": "success", **payload})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@data_bp.route("/api/data/pakistan/regression-seed")
def pakistan_regression_seed():
    """Fetch a regression-friendly Pakistan dataset from online sources."""
    try:
        start_year = int(request.args.get("start_year", 2000))
        end_year = int(request.args.get("end_year", 2024))
        payload = PakistanDataConnector().fetch_regression_seed(start_year, end_year)
        return jsonify(payload)
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }), 400


@data_bp.route("/api/data/pakistan/solar")
def pakistan_solar():
    """Fetch solar climatology for a Pakistan location."""
    try:
        location = request.args.get("location", "Islamabad")
        connector = PakistanDataConnector()
        if location in connector.PAKISTAN_LOCATIONS:
            coords = connector.PAKISTAN_LOCATIONS[location]
            latitude = float(coords["lat"])
            longitude = float(coords["lon"])
        else:
            latitude = float(request.args.get("latitude"))
            longitude = float(request.args.get("longitude"))

        payload = connector.fetch_solar_resource(latitude, longitude)
        payload["location"] = location
        return jsonify(payload)
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }), 400
