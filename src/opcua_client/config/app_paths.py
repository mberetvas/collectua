from __future__ import annotations

from pathlib import Path


def collectua_root_dir() -> Path:
    """Canonical root directory for collectua persisted data."""
    return Path.home() / ".collectua"


def collectua_connections_dir() -> Path:
    return collectua_root_dir() / "connections"


def collectua_certs_base_dir() -> Path:
    return collectua_root_dir() / "certs"


def collectua_logs_dir() -> Path:
    return collectua_root_dir() / "logs"


def collectua_tui_dir() -> Path:
    return collectua_root_dir() / "tui"

