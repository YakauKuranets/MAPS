"""Compatibility namespace for legacy `app.security.*` imports."""

from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "security"
__path__.append(str(_pkg_root))
