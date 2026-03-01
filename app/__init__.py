"""PLAYE STUDIO PRO — Flask application factory.

Creates and configures the Flask application with all blueprints,
extensions, security headers, and CLI commands.
"""

from __future__ import annotations

import logging
import os

from compat_flask import Flask
from flask import render_template

from app.config import Config

logger = logging.getLogger(__name__)


def _apply_security_headers(app: Flask) -> None:
    """Add security headers to every response."""

    @app.after_request
    def _set_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://unpkg.com https://cdn.jsdelivr.net "
            "https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com "
            "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
            "https://fonts.googleapis.com; "
            "img-src 'self' data: blob: "
            "https://*.tile.openstreetmap.org "
            "https://*.basemaps.cartocdn.com https://unpkg.com; "
            "connect-src 'self' ws: wss: https:; "
            "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
            "object-src 'none'",
        )
        # Strip fingerprint headers
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)
        return response


def create_app(config_class: type = Config) -> Flask:
    """Flask application factory.

    Args:
        config_class: Configuration class
            (DevelopmentConfig / ProductionConfig / TestingConfig)

    Returns:
        Configured Flask application with all blueprints registered.
    """
    app = Flask(
        __name__,
        template_folder=os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "templates"
        ),
        static_folder=os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "static"
        ),
    )
    app.config.from_object(config_class)

    # ── Extensions ────────────────────────────────────────────
    from app.extensions import init_extensions

    init_extensions(app)

    # ── Security headers ──────────────────────────────────────
    _apply_security_headers(app)

    # ── Blueprints ────────────────────────────────────────────
    from importlib import import_module

    def _load_bp(module_name: str, attr: str = "bp"):
        try:
            module = import_module(module_name)
            return getattr(module, attr)
        except Exception as exc:
            logger.warning(
                "[create_app] blueprint '%s' skipped: %s", module_name, exc
            )
            return None

    # Blueprints with url_prefix already set
    for module_name in [
        "app.admin_users",
        "app.analytics",
        "app.chat",
        "app.event_chat",
        "app.handshake",
        "app.incidents",
        "app.maintenance",
        "app.notifications",
        "app.realtime",
        "app.terminals",
        "app.video",
    ]:
        bp_obj = _load_bp(module_name)
        if bp_obj is not None:
            app.register_blueprint(bp_obj)

    # Blueprints that need explicit prefix mapping
    prefix_blueprints = [
        ("app.addresses", "/api"),
        ("app.admin", "/api/admin"),
        ("app.auth", "/api/auth"),
        ("app.bot", "/api/bot"),
        ("app.general", "/api"),
        ("app.geocode", "/api"),
        ("app.objects", "/api"),
        ("app.pending", "/api"),
        ("app.requests", "/api"),
        ("app.audit.routes", "/api/audit"),
        ("app.offline", "/api"),
        ("app.service_access", "/api/service-access"),
        ("app.system", "/api/system"),
        ("app.duty", None),
    ]
    for module_name, url_prefix in prefix_blueprints:
        bp_obj = _load_bp(module_name)
        if bp_obj is None:
            continue
        if url_prefix is None:
            app.register_blueprint(bp_obj)
        else:
            app.register_blueprint(bp_obj, url_prefix=url_prefix)

    # ── Observability ─────────────────────────────────────────
    try:
        from app.observability.metrics import register_metrics

        register_metrics(app)
    except Exception:
        pass

    # Backward-compatible CSRF helper for templates that call csrf_token()
    app.jinja_env.globals.setdefault("csrf_token", lambda: "")

    app.jinja_env.globals.setdefault("vite_asset", lambda _path: None)

    # ── Root route → index.html (main map interface) ──────────
    @app.route("/")
    def index():
        return render_template("index.html")

    # ── Health / Ready ────────────────────────────────────────
    @app.route("/health")
    def health():
        return "", 204

    @app.route("/ready")
    def ready():
        return {"status": "ready"}, 200

    # ── CLI commands ──────────────────────────────────────────
    try:
        from app.commands import register_commands

        register_commands(app)
    except Exception:
        pass

    # ── Database init ─────────────────────────────────────────
    with app.app_context():
        from app.extensions import db

        try:
            db.create_all()
        except Exception as exc:
            logger.warning("[create_app] db.create_all skipped: %s", exc)

    logger.warning("[SYSTEM] PLAYE Command Center v5 initialised (Flask factory).")
    return app
