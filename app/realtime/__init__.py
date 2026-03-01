"""Compatibility namespace for legacy `app.realtime.*` imports."""

from pathlib import Path

from compat_flask import Blueprint

_pkg_root = Path(__file__).resolve().parents[2] / "realtime"
__path__.append(str(_pkg_root))

bp = Blueprint("realtime", __name__, url_prefix="/api/realtime")


def send_alert_to_dashboard(alert_data: dict) -> None:
    """Отправить событие алерта во все realtime-клиенты панели."""
    from app.sockets import broadcast_event_sync

    broadcast_event_sync("alert", alert_data)
