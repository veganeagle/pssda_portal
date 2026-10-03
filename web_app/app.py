import os

from web_app import create_app

app = create_app()

if __name__ == "__main__":
    # Off by default — Werkzeug's debug mode exposes an in-browser Python
    # console (EVALEX) on any unhandled exception, which is a remote-code-
    # execution path if this ever runs anywhere but localhost. Opt in
    # explicitly for local development: PSSDA_DEBUG=1 python -m web_app.app
    debug = os.environ.get("PSSDA_DEBUG") == "1"
    print("\nOPSCI.ca running at: http://127.0.0.1:5000/")
    app.run(debug=debug, use_reloader=False)
