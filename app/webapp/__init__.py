"""Compatibility namespace for legacy `app.webapp.*` imports."""

from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "webapp"
__path__.append(str(_pkg_root))
