from flask import Flask, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix
from access.home_dashboard import get_year_range
from web_app.formatting import proper_case
from web_app.rate_limit import limiter
from web_app.seo import is_indexable
from web_app.views import (
    combo_bp, compare_bp, employee_bp, employer_bp, home_bp, pages_bp, position_bp, sector_bp, top_earners_bp,
)


def create_app():
    app = Flask(__name__)
    # Trusts exactly one proxy hop (Caddy/nginx) for the real client IP, which
    # both per-IP limiters key on — gunicorn must bind to 127.0.0.1 only, or a
    # client could spoof X-Forwarded-For directly.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.register_blueprint(home_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(employer_bp)
    app.register_blueprint(position_bp)
    app.register_blueprint(sector_bp)
    app.register_blueprint(top_earners_bp)
    app.register_blueprint(combo_bp)
    app.register_blueprint(compare_bp)
    app.register_blueprint(pages_bp)
    app.jinja_env.filters["proper"] = proper_case

    limiter.init_app(app)

    @app.context_processor
    def site_years():
        return {"site_years": get_year_range(), "indexable": is_indexable()}

    @app.after_request
    def robots_header(resp):
        if not is_indexable():
            resp.headers["X-Robots-Tag"] = "noindex"
        return resp

    @app.errorhandler(429)
    def rate_limited(e):
        return render_template("rate_limited.html"), 429

    @app.errorhandler(404)
    def not_found(e):
        return render_template("not_found.html", what="page", key=request.path), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("server_error.html"), 500

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app
