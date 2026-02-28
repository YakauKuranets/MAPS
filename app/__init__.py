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
    # Core API (no prefix needed — blueprints define their own)
    from app.addresses import bp as addresses_bp
    from app.admin import bp as admin_bp
    from app.admin_users import bp as admin_users_bp
    from app.analytics import bp as analytics_bp
    from app.audit.routes import bp as audit_bp
    from app.auth import bp as auth_bp
    from app.bot import bp as bot_bp
    from app.chat import bp as chat_bp
    from app.duty import bp as duty_bp
    from app.event_chat import bp as event_chat_bp
    from app.general import bp as general_bp
    from app.geocode import bp as geocode_bp
    from app.handshake import bp as handshake_bp
    from app.incidents import bp as incidents_bp
    from app.maintenance import bp as maintenance_bp
    from app.notifications import bp as notifications_bp
    from app.objects import bp as objects_bp
    from app.offline import bp as offline_bp
    from app.pending import bp as pending_bp
    from app.realtime import bp as realtime_bp
    from app.requests import bp as requests_bp
    from app.service_access import bp as service_access_bp
    from app.system import bp as system_bp
    from app.terminals import bp as terminals_bp
    from app.video import bp as video_bp

    # Blueprints with url_prefix already set
    for bp_obj in [
        admin_users_bp,
        analytics_bp,
        chat_bp,
        event_chat_bp,
        handshake_bp,
        incidents_bp,
        maintenance_bp,
        notifications_bp,
        realtime_bp,
        terminals_bp,
        video_bp,
    ]:
        app.register_blueprint(bp_obj)

    # Blueprints that need /api prefix
    app.register_blueprint(addresses_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(bot_bp, url_prefix="/api/bot")
    app.register_blueprint(general_bp, url_prefix="/api")
    app.register_blueprint(geocode_bp, url_prefix="/api")
    app.register_blueprint(objects_bp, url_prefix="/api")
    app.register_blueprint(pending_bp, url_prefix="/api")
    app.register_blueprint(requests_bp, url_prefix="/api")
    app.register_blueprint(audit_bp, url_prefix="/api/audit")
    app.register_blueprint(offline_bp, url_prefix="/api")
    app.register_blueprint(service_access_bp, url_prefix="/api/service-access")
    app.register_blueprint(system_bp, url_prefix="/api/system")
    app.register_blueprint(duty_bp)

    # ── Observability ─────────────────────────────────────────
    try:
        from app.observability.metrics import register_metrics

        register_metrics(app)
    except Exception:
        pass

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

        db.create_all()

    logger.warning("[SYSTEM] PLAYE Command Center v5 initialised (Flask factory).")
    return app
