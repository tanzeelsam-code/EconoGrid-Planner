"""
Flask Application Factory.

Creates and configures the Flask app with route blueprints,
template directory, and error handlers.
"""

import os
import sys
from flask import Flask

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import SECRET_KEY, OUTPUT_DIR, UPLOAD_DIR


def create_app() -> Flask:
    """
    Create and configure the Flask application.

    Returns:
        Configured Flask app instance.
    """
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["OUTPUT_DIR"] = str(OUTPUT_DIR)
    app.config["UPLOAD_DIR"] = str(UPLOAD_DIR)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload

    # Ensure directories exist
    os.makedirs(app.config["OUTPUT_DIR"], exist_ok=True)
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    # Register blueprints
    from .routes.regression_routes import regression_bp
    from .routes.scenario_routes import scenario_bp
    from .routes.financial_routes import financial_bp

    app.register_blueprint(regression_bp, url_prefix="/api/regression")
    app.register_blueprint(scenario_bp, url_prefix="/api/scenario")
    app.register_blueprint(financial_bp, url_prefix="/api/financial")

    from .routes.upload_routes import upload_bp
    app.register_blueprint(upload_bp, url_prefix="/api/upload")

    # Register main routes
    from flask import render_template, jsonify

    @app.route("/")
    def index():
        """Dashboard home page."""
        return render_template("index.html")

    @app.route("/regression")
    def regression_page():
        return render_template("regression.html")

    @app.route("/scenario")
    def scenario_page():
        return render_template("scenario.html")

    @app.route("/financial")
    def financial_page():
        return render_template("financial.html")

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "app": "EconoGrid Planner"})

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

    return app
