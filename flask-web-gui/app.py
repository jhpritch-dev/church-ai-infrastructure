"""
Episcopal Bulletin Dashboard - Flask Web GUI
Connects to the bulletin-api (FastAPI) backend for bulletin generation and listing.
"""

import os
import requests
from flask import Flask, render_template, jsonify, request, redirect, url_for

app = Flask(__name__)

# Configuration from environment
BULLETIN_API_URL = os.getenv("BULLETIN_API_URL", "http://bulletin-api:8000")
PAPERLESS_URL = os.getenv("PAPERLESS_URL", "http://paperless:8000")
NOTEBOOK_URL = os.getenv("NOTEBOOK_URL", "http://open-notebook:3030")


@app.route("/")
def index():
    """Main dashboard - list bulletins and show generate form."""
    bulletins = []
    api_status = "unknown"
    error = None

    try:
        # Check API health
        health_resp = requests.get(f"{BULLETIN_API_URL}/health", timeout=5)
        if health_resp.ok:
            api_status = "healthy"

        # Fetch bulletins
        resp = requests.get(f"{BULLETIN_API_URL}/bulletins", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        bulletins = data.get("bulletins", [])
    except requests.ConnectionError:
        error = f"Cannot connect to Bulletin API at {BULLETIN_API_URL}"
        api_status = "offline"
    except requests.RequestException as e:
        error = f"API error: {e}"
        api_status = "error"

    return render_template(
        "index.html",
        bulletins=bulletins,
        error=error,
        api_status=api_status,
        api_url=BULLETIN_API_URL,
    )


@app.route("/generate", methods=["GET"])
def generate_form():
    """Show the bulletin generation form (proxied from API)."""
    try:
        resp = requests.get(f"{BULLETIN_API_URL}/form", timeout=10)
        return resp.text
    except requests.RequestException:
        return redirect(url_for("index"))


@app.route("/generate", methods=["POST"])
def generate_bulletin():
    """Proxy form submission to the bulletin API."""
    try:
        form_data = request.form.to_dict()
        resp = requests.post(
            f"{BULLETIN_API_URL}/generate",
            data=form_data,
            timeout=30,
        )
        if resp.ok:
            result = resp.json()
            download_url = result.get("download_url", "")
            # Redirect to download through the API
            return redirect(f"{BULLETIN_API_URL}{download_url}")
        else:
            return f"<h1>Generation Failed</h1><p>{resp.text}</p><a href='/'>Back</a>", 500
    except requests.RequestException as e:
        return f"<h1>Connection Error</h1><p>{e}</p><a href='/'>Back</a>", 502


@app.route("/health")
def health():
    """Health check for Docker Compose."""
    return jsonify(
        status="ok",
        bulletin_api=BULLETIN_API_URL,
    )


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_RUN_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_RUN_PORT", 5000)),
        debug=os.getenv("FLASK_ENV", "production") == "development",
    )
