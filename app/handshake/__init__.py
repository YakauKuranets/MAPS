"""Handshake upload API blueprint."""

from compat_flask import Blueprint

bp = Blueprint("handshake", __name__, url_prefix="/api/video/handshake")

from . import routes  # noqa: E402,F401
