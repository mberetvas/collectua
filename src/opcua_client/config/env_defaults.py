from __future__ import annotations

import os

from functools import lru_cache
from pathlib import Path


ENV_FILE_OVERRIDE = "OPCUA_ENV_FILE"


def _strip_wrapping_quotes(value: str) -> str:
    """Remove a single pair of matching wrapping quotes from a value."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a minimal .env file into a string mapping."""
    payload: dict[str, str] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line.removeprefix("export ").strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        payload[key] = _strip_wrapping_quotes(value.strip())

    return payload


@lru_cache(maxsize=1)
def load_env_defaults() -> dict[str, str]:
    """Load default values from the package-local .env file or an override path."""
    candidate_paths: list[Path] = []

    override_path = os.getenv(ENV_FILE_OVERRIDE, "").strip()
    if override_path:
        candidate_paths.append(Path(override_path).expanduser())

    candidate_paths.append(Path(__file__).resolve().with_name(".env"))

    for path in candidate_paths:
        if path.exists() and path.is_file():
            return _parse_env_file(path)

    return {}


def clear_env_defaults_cache() -> None:
    """Clear the cached .env payload, primarily for tests."""
    load_env_defaults.cache_clear()


def get_str(name: str, default: str = "") -> str:
    """Return a string value from the process environment or package defaults."""
    if name in os.environ:
        return os.environ[name]
    return load_env_defaults().get(name, default)


def get_bool(name: str, default: bool = False) -> bool:
    """Return a boolean value from the process environment or package defaults."""
    raw = get_str(name, "")
    if raw == "":
        return default

    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def get_int(name: str, default: int) -> int:
    """Return an integer value from the process environment or package defaults."""
    raw = get_str(name, "")
    if raw == "":
        return default

    try:
        return int(raw)
    except ValueError:
        return default


def get_float(name: str, default: float) -> float:
    """Return a float value from the process environment or package defaults."""
    raw = get_str(name, "")
    if raw == "":
        return default

    try:
        return float(raw)
    except ValueError:
        return default


def get_str_list(name: str, default: list[str] | None = None) -> list[str]:
    """Return a comma-separated string list from the process environment or package defaults."""
    raw = get_str(name, "")
    if raw == "":
        return list(default or [])

    values: list[str] = []
    for item in raw.split(","):
        token = item.strip()
        if token:
            values.append(token)
    return values


def get_int_list(name: str, default: list[int] | None = None) -> list[int]:
    """Return a comma-separated integer list from the process environment or package defaults."""
    raw = get_str(name, "")
    if raw == "":
        return list(default or [])

    values: list[int] = []
    for item in raw.split(","):
        token = item.strip()
        if not token:
            continue
        try:
            values.append(int(token))
        except ValueError:
            continue
    return values


def get_path(name: str, default: str, *, relative_to_cwd: bool = False) -> Path:
    """Return a path value from the process environment or package defaults."""
    path = Path(get_str(name, default)).expanduser()
    if relative_to_cwd and not path.is_absolute():
        return Path.cwd() / path
    return path


def get_formatted_str(name: str, default: str, **kwargs: str) -> str:
    """Return a string value and format it with keyword replacements when possible."""
    template = get_str(name, default)
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return template

