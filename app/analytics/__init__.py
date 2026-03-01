"""Compatibility namespace for legacy `app.analytics.*` imports."""

from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "analytics"
__path__.append(str(_pkg_root))
