"""Compatibility namespace for legacy `app.tasks.*` imports."""

from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "tasks"
__path__.append(str(_pkg_root))


__all__ = ["process_voice_incident"]


def __getattr__(name: str):
    if name == "process_voice_incident":
        from tasks import process_voice_incident

        return process_voice_incident
    raise AttributeError(name)
