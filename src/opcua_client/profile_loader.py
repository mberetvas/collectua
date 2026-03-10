from __future__ import annotations

from pathlib import Path

import yaml

PROFILE_KEYS = {
    "url",
    "timeout",
    "session_timeout",
    "request_timeout",
    "username",
    "password",
    "auth_policy",
    "security_mode",
    "server_cert",
    "trust_cert",
    "logging",
}


def profile_search_dirs() -> list[Path]:
    return [
        Path.cwd() / "connections",
        Path("~/.config/opcua-client/connections").expanduser(),
    ]


def list_profiles() -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    for directory in profile_search_dirs():
        if not directory.exists() or not directory.is_dir():
            continue

        for file_path in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
            name = file_path.stem
            if name not in seen:
                seen.add(name)
                names.append(name)

    return names


def _resolve_profile_path(profile_name: str) -> Path:
    for directory in profile_search_dirs():
        for suffix in (".yaml", ".yml"):
            file_path = directory / f"{profile_name}{suffix}"
            if file_path.exists() and file_path.is_file():
                return file_path

    raise FileNotFoundError(
        f"Connection profile '{profile_name}' not found in ./connections/ or ~/.config/opcua-client/connections/"
    )


def resolve_profile_path(profile_name: str) -> Path:
    """
    Public helper to resolve a profile name to its underlying YAML file path.
    """
    return _resolve_profile_path(profile_name)


def load_profile(profile_name: str) -> dict:
    profile_path = _resolve_profile_path(profile_name)

    try:
        with profile_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in profile '{profile_name}': {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Profile '{profile_name}' must contain a YAML mapping at the top level")

    unknown_keys = sorted(set(payload.keys()) - PROFILE_KEYS)
    if unknown_keys:
        raise ValueError(f"Profile '{profile_name}' contains unknown fields: {', '.join(unknown_keys)}")

    return payload
