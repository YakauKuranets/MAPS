"""Compatibility namespace for legacy `app.audit.*` imports."""

from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "audit"
__path__.append(str(_pkg_root))
