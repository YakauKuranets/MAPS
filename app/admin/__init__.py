"""Compatibility namespace for legacy `app.admin.*` imports."""

from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "admin"
__path__.append(str(_pkg_root))
