"""Compatibility namespace for legacy `app.terminals.*` imports."""

from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "terminals"
__path__.append(str(_pkg_root))
