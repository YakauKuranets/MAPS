"""Compatibility namespace for legacy `app.diagnostics.*` imports."""

from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "diagnostics"
__path__.append(str(_pkg_root))
