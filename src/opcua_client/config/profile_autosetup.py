from __future__ import annotations

import asyncio
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import yaml
from asyncua import Client, ua

from .env_defaults import get_float, get_int, get_path
from .profile_loader import load_profile, profile_search_dirs, resolve_profile_path


@dataclass(frozen=True)
class DiscoveredMode:
    auth_policy: str
    security_mode: str
    allows_anonymous: bool
    allows_username: bool


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


def url_profile_name(url: str) -> str:
    """
    Derive a deterministic, filesystem-safe profile name from the full URL.
    """
    normalized = _normalize_url(url)
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:8]
    return f"url-{digest}"


def _candidate_profile_paths(profile_name: str) -> Iterable[Path]:
    for directory in profile_search_dirs():
        for suffix in (".yaml", ".yml"):
            yield directory / f"{profile_name}{suffix}"


def find_existing_profile_for_url(url: str) -> str | None:
    """
    Return the profile name for this URL if a deterministic URL-based profile
    already exists, else None.
    """
    name = url_profile_name(url)
    for path in _candidate_profile_paths(name):
        if path.exists() and path.is_file():
            return name
    return None


def _choose_profile_directory_for_creation() -> Path:
    """
    Prefer ./connections/ under the current working directory, falling back to
    ~/.config/opcua-client/connections/ if needed.
    """
    cwd_dir = get_path("OPCUA_PROFILE_DIR", "connections", relative_to_cwd=True)
    try:
        cwd_dir.mkdir(parents=True, exist_ok=True)
        return cwd_dir
    except Exception:
        pass

    config_dir = get_path("OPCUA_FALLBACK_PROFILE_DIR", "~/.config/opcua-client/connections")
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


async def _discover_server_security_options(url: str) -> List[DiscoveredMode]:
    client = Client(url=url)
    endpoints = await client.connect_and_get_server_endpoints()

    options: dict[tuple[str, str], DiscoveredMode] = {}

    for ep in endpoints:
        policy_uri = getattr(ep, "SecurityPolicyUri", "") or ""
        # Extract short policy name from URI, e.g. ...#Basic256Sha256
        policy_short = policy_uri.rsplit("#", 1)[-1] if "#" in policy_uri else policy_uri or "None"

        mode = getattr(ep, "SecurityMode", ua.MessageSecurityMode.None_)
        mode_name = mode.name
        security_mode = "None_" if mode_name == "None" else mode_name

        allows_anonymous = False
        allows_username = False

        for token in getattr(ep, "UserIdentityTokens", []) or []:
            token_type = getattr(token, "TokenType", None)
            if token_type == ua.UserTokenType.Anonymous:
                allows_anonymous = True
            if token_type == ua.UserTokenType.UserName:
                allows_username = True

        key = (policy_short, security_mode)
        existing = options.get(key)
        combined = DiscoveredMode(
            auth_policy=policy_short,
            security_mode=security_mode,
            allows_anonymous=allows_anonymous or (existing.allows_anonymous if existing else False),
            allows_username=allows_username or (existing.allows_username if existing else False),
        )
        options[key] = combined

    # Sort for stable presentation: policy then mode
    return sorted(options.values(), key=lambda o: (o.auth_policy, o.security_mode))


def _prompt_choice(modes: List[DiscoveredMode]) -> DiscoveredMode:
    print("Discovered security modes for this OPC UA server:")
    for idx, m in enumerate(modes, start=1):
        auth = []
        if m.allows_anonymous:
            auth.append("anonymous")
        if m.allows_username:
            auth.append("username/password")
        auth_str = ", ".join(auth) if auth else "certificate/other"
        print(f"  {idx}) {m.auth_policy} / {m.security_mode}  [{auth_str}]")

    while True:
        choice = input("Select security option [1-{n}]: ".format(n=len(modes))).strip()
        if not choice.isdigit():
            print("Please enter a number.")
            continue
        idx = int(choice)
        if 1 <= idx <= len(modes):
            return modes[idx - 1]
        print("Invalid selection.")


def _prompt_credentials(mode: DiscoveredMode) -> tuple[str, str]:
    from getpass import getpass

    username = ""
    password = ""

    if mode.allows_username:
        use_user = input("Use username/password authentication? [y/N]: ").strip().lower()
        if use_user == "y":
            username = input("Username: ").strip()
            password = getpass("Password: ")

    return username, password


def ensure_profile_for_url_interactive(url: str) -> str:
    """
    Ensure a connection profile exists for the given URL.

    If a deterministic URL-based profile already exists, its name is returned.
    Otherwise, this function performs endpoint discovery, prompts the user to
    select a security mode and optionally credentials, creates a new profile
    YAML file, and returns its name.
    """
    existing = find_existing_profile_for_url(url)
    if existing:
        try:
            existing_payload = load_profile(existing)
            existing_url = str(existing_payload.get("url", ""))
            if existing_url.startswith("opc.tcp://"):
                return existing
        except Exception:
            pass

    if not sys.stdin.isatty():
        raise RuntimeError(
            "Interactive TUI auto-setup requires a TTY for prompts. "
            "Provide --connection-profile explicitly in non-interactive environments."
        )

    print(f"No existing connection profile found for URL: {url}")
    print("Discovering server endpoints...")

    try:
        modes = asyncio.run(_discover_server_security_options(url))
    except Exception as exc:
        raise RuntimeError(f"Failed to discover OPC UA endpoints for {url}: {exc}") from exc

    if not modes:
        raise RuntimeError(f"No usable security modes discovered for OPC UA server at {url}")

    chosen = _prompt_choice(modes)
    username, password = _prompt_credentials(chosen)

    profile_name = url_profile_name(url)
    directory = _choose_profile_directory_for_creation()
    profile_path = directory / f"{profile_name}.yaml"

    payload: dict = {
        "url": url,
        "timeout": get_float("OPCUA_TIMEOUT", 30.0),
        "session_timeout": get_int("OPCUA_SESSION_TIMEOUT", 60000),
        "request_timeout": get_int("OPCUA_REQUEST_TIMEOUT", 20000),
        "username": username,
        "password": password,
        "auth_policy": chosen.auth_policy,
        "security_mode": chosen.security_mode,
        # Server certificate metadata and trust flag are populated lazily on first trust.
        "server_cert": "",
        "trust_cert": False,
    }

    with profile_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)

    print(f"Created connection profile '{profile_name}' at {profile_path}")
    return profile_name

