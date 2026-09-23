from flask import Flask
from web_app.formatting import proper_case
from web_app.views import profile_bp


def create_app():
    app = Flask(__name__)
    app.register_blueprint(profile_bp)
    app.jinja_env.filters["proper"] = proper_case

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app
