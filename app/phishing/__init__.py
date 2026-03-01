"""Compatibility namespace for legacy `app.phishing.*` imports."""

from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "phishing"
__path__.append(str(_pkg_root))
