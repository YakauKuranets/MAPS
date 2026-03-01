"""Compatibility namespace for legacy `app.osint.*` imports."""

from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "osint"
__path__.append(str(_pkg_root))
