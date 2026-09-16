from flask import Flask
from web_app.views import api_bp, ui_bp
from web_app.services.dropdown_service import dropdown_cache


def create_app():
    """Factory for creating the Flask app."""
    app = Flask(__name__)

    # Register blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(ui_bp)

    # Basic health check
    @app.route("/health")
    def health():
        return {
            "status": "ok",
            "cache_counts": {k: len(v) for k, v in dropdown_cache.items()}
        }

    return app
