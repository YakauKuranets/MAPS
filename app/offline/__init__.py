"""Compatibility namespace for legacy `app.offline.*` imports."""

from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "offline"
__path__.append(str(_pkg_root))
