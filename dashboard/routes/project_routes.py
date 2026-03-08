"""
Project persistence and report export routes.
"""

import os
import sys
import traceback

from flask import Blueprint, jsonify, request, send_file

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from utils.project_store import ProjectStore
from utils.report_generator import ProjectReportGenerator


project_bp = Blueprint("projects", __name__)


@project_bp.route("", methods=["GET"])
def list_projects():
    """List saved projects."""
    try:
        store = ProjectStore()
        return jsonify({"status": "success", "projects": store.list_projects()})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@project_bp.route("/save", methods=["POST"])
def save_project():
    """Save a versioned project snapshot."""
    try:
        payload = request.get_json(silent=True) or {}
        project_name = (payload.get("project_name") or "").strip()
        module = payload.get("module")
        inputs = payload.get("inputs") or {}
        results = payload.get("results") or {}
        notes = payload.get("notes", "")

        if not project_name:
            return jsonify({"status": "error", "message": "project_name is required"}), 400
        if module not in {"regression", "scenario", "financial"}:
            return jsonify({"status": "error", "message": "Valid module is required"}), 400

        project = ProjectStore().save_snapshot(
            project_name=project_name,
            module=module,
            inputs=inputs,
            results=results,
            notes=notes,
        )
        return jsonify({"status": "success", "project": project})
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }), 400


@project_bp.route("/<project_id>", methods=["GET"])
def get_project(project_id):
    """Fetch a saved project."""
    try:
        project = ProjectStore().get_project(project_id)
        return jsonify({"status": "success", "project": project})
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "Project not found"}), 404
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@project_bp.route("/<project_id>/versions", methods=["GET"])
def get_versions(project_id):
    """List project versions, optionally filtered by module."""
    try:
        module = request.args.get("module")
        versions = ProjectStore().get_versions(project_id, module=module)
        return jsonify({"status": "success", "versions": versions})
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "Project not found"}), 404
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@project_bp.route("/<project_id>/latest/<module>", methods=["GET"])
def get_latest_version(project_id, module):
    """Fetch the latest version for a single module."""
    try:
        version = ProjectStore().get_latest_version(project_id, module)
        if version is None:
            return jsonify({"status": "error", "message": "Module version not found"}), 404
        return jsonify({"status": "success", "version": version})
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "Project not found"}), 404
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@project_bp.route("/<project_id>/report", methods=["GET"])
def download_report(project_id):
    """Generate and download a board-style PDF report for a project."""
    try:
        store = ProjectStore()
        project = store.get_project(project_id)
        filepath = ProjectReportGenerator().generate(project)
        return send_file(filepath, as_attachment=True, download_name=filepath.name)
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "Project not found"}), 404
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }), 400
