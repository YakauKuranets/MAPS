"""Compatibility namespace for legacy `app.incidents.*` imports."""

from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "incidents"
__path__.append(str(_pkg_root))
