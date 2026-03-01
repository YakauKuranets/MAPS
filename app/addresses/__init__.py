"""Compatibility namespace for legacy `app.addresses.*` imports."""

from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "addresses"
__path__.append(str(_pkg_root))
