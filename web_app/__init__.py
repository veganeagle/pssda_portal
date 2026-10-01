from flask import Flask, render_template
from web_app.formatting import proper_case
from web_app.rate_limit import limiter
from web_app.views import combo_bp, employee_bp, employer_bp, home_bp, position_bp, top_earners_bp


def create_app():
    app = Flask(__name__)
    app.register_blueprint(home_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(employer_bp)
    app.register_blueprint(position_bp)
    app.register_blueprint(top_earners_bp)
    app.register_blueprint(combo_bp)
    app.jinja_env.filters["proper"] = proper_case

    limiter.init_app(app)

    @app.errorhandler(429)
    def rate_limited(e):
        return render_template("rate_limited.html"), 429

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app
