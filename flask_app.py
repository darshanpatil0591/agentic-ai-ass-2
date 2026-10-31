"""Flask interface for the Assignment 2 Safe Student Support Agent.

This file only replaces the Streamlit *interface*. Authentication, ownership
checks, the approval gate and audit logging all stay in the existing
support_agent package (auth.py, service.py, database.py). Every route below
re-checks the signed-in role on the server; the browser is never trusted.
"""

from __future__ import annotations

import os
import secrets
import time
from functools import wraps

from flask import Flask, jsonify, render_template, request, session

from support_agent.agent import run_agent
from support_agent.auth import authenticate
from support_agent.config import ConfigurationError, load_settings
from support_agent.database import initialize
from support_agent.service import StudentService

ACCOUNTS = [
    {"username": "student1", "name": "Asha Sharma", "role_label": "Student", "initials": "AS"},
    {"username": "student2", "name": "Rahul Mehta", "role_label": "Student", "initials": "RM"},
    {"username": "reviewer", "name": "Student Services Reviewer", "role_label": "Reviewer", "initials": "SR"},
]
ACCOUNT_BY_NAME = {account["username"]: account for account in ACCOUNTS}

MAX_QUESTION_CHARS = 2_000
MAX_EMAIL_CHARS = 254
LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_FAILURES = 5

app = Flask(__name__)
app.config.update(
    # Set FLASK_SECRET_KEY in your environment to keep sessions across restarts.
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=16 * 1024,
)

try:
    SETTINGS = load_settings()
    initialize(SETTINGS)
    STARTUP_ERROR = None
except ConfigurationError as exc:
    SETTINGS = None
    STARTUP_ERROR = str(exc)

# The authenticated principal lives on the server. The browser cookie only
# carries an opaque random id, never the role or username.
_PRINCIPALS: dict[str, object] = {}
_FAILED_LOGINS: dict[str, list[float]] = {}


# ----------------------------------------------------------------- helpers
def current_principal():
    token = session.get("sid")
    return _PRINCIPALS.get(token) if token else None


def user_view(principal) -> dict:
    account = ACCOUNT_BY_NAME.get(principal.username, {})
    return {
        "username": principal.username,
        "role": principal.role,
        "name": account.get("name", principal.username),
        "initials": account.get("initials", principal.username[:2].upper()),
    }


def service_for(principal) -> StudentService:
    return StudentService(SETTINGS.database_path, principal)


def clean_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def to_records(rows) -> list[dict]:
    """Turn a DataFrame, list of dicts or list of sqlite rows into plain JSON."""
    if hasattr(rows, "to_dict"):
        try:
            rows = rows.to_dict(orient="records")
        except TypeError:
            rows = rows.to_dict()
    records = []
    for row in rows or []:
        record = row if isinstance(row, dict) else dict(row)
        records.append({str(key): clean_value(val) for key, val in record.items()})
    return records


def too_many_failures(ip: str) -> bool:
    now = time.time()
    recent = [t for t in _FAILED_LOGINS.get(ip, []) if now - t < LOGIN_WINDOW_SECONDS]
    _FAILED_LOGINS[ip] = recent
    return len(recent) >= LOGIN_MAX_FAILURES


def guarded(role: str | None = None):
    """Require a signed-in user, and optionally a specific role."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            principal = current_principal()
            if principal is None:
                return jsonify(error="Please sign in again."), 401
            is_reviewer = principal.role == "reviewer"
            if (role == "reviewer" and not is_reviewer) or (role == "student" and is_reviewer):
                return jsonify(error="Your account is not permitted to do this."), 403
            return view(principal, *args, **kwargs)

        return wrapper

    return decorator


# --------------------------------------------------------- request hooks
@app.before_request
def csrf_protect():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf", "")
        if not expected or not secrets.compare_digest(sent.encode(), expected.encode()):
            return jsonify(error="Your page expired. Refresh and try again."), 400
    return None


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "script-src 'self'; img-src 'self' data:; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    return response


# ------------------------------------------------------------------ pages
@app.get("/")
def index():
    session.setdefault("csrf", secrets.token_urlsafe(32))
    principal = current_principal()
    return render_template(
        "index.html",
        csrf_token=session["csrf"],
        user=user_view(principal) if principal else None,
        accounts=ACCOUNTS,
        startup_error=STARTUP_ERROR,
        max_question=MAX_QUESTION_CHARS,
    )


# -------------------------------------------------------------- auth API
@app.post("/api/login")
def login():
    if SETTINGS is None:
        return jsonify(error="The app is not configured. Check your .env file."), 500

    ip = request.remote_addr or "unknown"
    if too_many_failures(ip):
        return jsonify(error="Too many failed attempts. Wait a few minutes and try again."), 429

    data = request.get_json(silent=True) or {}
    username = str(data.get("username", ""))
    password = str(data.get("password", ""))

    principal = authenticate(SETTINGS, username, password) if username in ACCOUNT_BY_NAME else None
    if not principal:
        _FAILED_LOGINS.setdefault(ip, []).append(time.time())
        return jsonify(error="Sign-in failed. Check the local password in your .env file."), 401

    _PRINCIPALS.pop(session.get("sid"), None)
    token = secrets.token_urlsafe(32)
    _PRINCIPALS[token] = principal
    session["sid"] = token
    session["csrf"] = secrets.token_urlsafe(32)
    _FAILED_LOGINS.pop(ip, None)
    return jsonify(ok=True)


@app.post("/api/logout")
def logout():
    _PRINCIPALS.pop(session.get("sid"), None)
    session.clear()
    return jsonify(ok=True)


# ----------------------------------------------------------- student API
@app.get("/api/account")
@guarded("student")
def account(principal):
    try:
        data = service_for(principal).my_fee_status()
    except Exception:
        app.logger.exception("Could not load account status")
        return jsonify(error="Could not load your account right now."), 500
    return jsonify(
        fee_status=clean_value(data["fee_status"]),
        scholarship_status=clean_value(data["scholarship_status"]),
    )


@app.post("/api/ask")
@guarded("student")
def ask(principal):
    data = request.get_json(silent=True) or {}
    question = str(data.get("question", "")).strip()[:MAX_QUESTION_CHARS]
    if not question:
        return jsonify(error="Type a question first."), 400
    try:
        result = run_agent(SETTINGS, principal, question)
    except Exception as exc:
        app.logger.exception("Agent request failed")
        return jsonify(error="Agent request failed: " + type(exc).__name__), 502

    tools = [t if isinstance(t, str) else str(getattr(t, "name", t)) for t in (result.tools or [])]
    return jsonify(
        answer=result.answer,
        latency_ms=result.latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        tools=tools,
    )


@app.post("/api/email-change")
@guarded("student")
def email_change(principal):
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip()[:MAX_EMAIL_CHARS]
    try:
        result = service_for(principal).request_email_change(email)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        app.logger.exception("Email change request failed")
        return jsonify(error="Could not submit your request right now."), 500
    return jsonify(message=clean_value(result["message"]), request_id=clean_value(result["request_id"]))


@app.get("/api/requests")
@guarded("student")
def my_requests(principal):
    try:
        rows = to_records(service_for(principal).my_requests())
    except Exception:
        app.logger.exception("Could not load request history")
        return jsonify(error="Could not load your request history."), 500
    return jsonify(rows=rows)


# ---------------------------------------------------------- reviewer API
@app.get("/api/pending")
@guarded("reviewer")
def pending(principal):
    try:
        rows = to_records(service_for(principal).pending_requests())
    except Exception:
        app.logger.exception("Could not load pending requests")
        return jsonify(error="Could not load the review queue."), 500
    return jsonify(rows=rows)


@app.post("/api/review")
@guarded("reviewer")
def review(principal):
    data = request.get_json(silent=True) or {}
    approve = data.get("approve")
    try:
        request_id = int(data.get("request_id"))
    except (TypeError, ValueError):
        return jsonify(error="Invalid request id."), 400
    if not isinstance(approve, bool):
        return jsonify(error="Invalid decision."), 400

    try:
        service_for(principal).review(request_id, approve)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        app.logger.exception("Review failed")
        return jsonify(error="The decision could not be saved."), 500

    message = (
        "Request approved and email update executed."
        if approve
        else "Request rejected. No student record was changed."
    )
    return jsonify(message=message)


if __name__ == "__main__":
    # Local use only: localhost binding, debug off so errors never leak details.
    app.run(host="127.0.0.1", port=5000, debug=False)
