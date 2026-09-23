from flask import Flask
from web_app.formatting import proper_case
from web_app.views import employee_bp, employer_bp, position_bp


def create_app():
    app = Flask(__name__)
    app.register_blueprint(employee_bp)
    app.register_blueprint(employer_bp)
    app.register_blueprint(position_bp)
    app.jinja_env.filters["proper"] = proper_case

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app
