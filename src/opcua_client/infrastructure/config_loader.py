from __future__ import annotations

from argparse import Namespace
from typing import Any

from opcua_client.domain.connection import OPCUAConnection
from opcua_client.config.profile_loader import load_profile
from opcua_client.config.runtime_config import RuntimeConfig


def load_connection_from_profile(profile_name: str) -> OPCUAConnection:
    payload = load_profile(profile_name)
    return OPCUAConnection.from_values(
        url=str(payload.get("url", "")),
        timeout=float(payload.get("timeout", 30.0)),
        session_timeout=int(payload.get("session_timeout", 60000)),
        request_timeout=int(payload.get("request_timeout", 20000)),
        security_mode=str(payload.get("security_mode", "None_")),
        auth_policy=str(payload.get("auth_policy", "None")),
        username=str(payload.get("username", "")),
        password=str(payload.get("password", "")),
        cert_file=str(payload.get("cert_file", "")),
        key_file=str(payload.get("key_file", "")),
        server_cert=str(payload.get("server_cert", "")),
        trust_cert=bool(payload.get("trust_cert", False)),
    )


def load_connection_from_cli_args(args: Namespace) -> OPCUAConnection:
    runtime_config = RuntimeConfig.from_namespace(args)
    connection = runtime_config.connection
    return OPCUAConnection.from_values(
        url=connection.url,
        timeout=connection.timeout,
        session_timeout=connection.session_timeout,
        request_timeout=connection.request_timeout,
        security_mode=connection.security_mode,
        auth_policy=connection.auth_policy,
        username=connection.username,
        password=connection.password,
        cert_file=connection.cert_file,
        key_file=connection.key_file,
        server_cert=connection.server_cert,
        trust_cert=connection.trust_cert,
    )


def merge_configs(profile: dict[str, Any], cli_args: Namespace, env_defaults: dict[str, Any]) -> OPCUAConnection:
    merged: dict[str, Any] = {
        "url": env_defaults.get("OPCUA_URL", ""),
        "timeout": env_defaults.get("OPCUA_TIMEOUT", 30.0),
        "session_timeout": env_defaults.get("OPCUA_SESSION_TIMEOUT", 60000),
        "request_timeout": env_defaults.get("OPCUA_REQUEST_TIMEOUT", 20000),
        "auth_policy": env_defaults.get("OPCUA_AUTH_POLICY", "None"),
        "security_mode": env_defaults.get("OPCUA_SECURITY_MODE", "None_"),
        "username": env_defaults.get("OPCUA_USERNAME", ""),
        "password": env_defaults.get("OPCUA_PASSWORD", ""),
        "cert_file": env_defaults.get("OPCUA_CERT_FILE", ""),
        "key_file": env_defaults.get("OPCUA_KEY_FILE", ""),
        "server_cert": env_defaults.get("OPCUA_SERVER_CERT", ""),
        "trust_cert": env_defaults.get("OPCUA_TRUST_CERT", False),
    }
    merged.update(profile)

    for key in list(merged.keys()):
        if hasattr(cli_args, key):
            value = getattr(cli_args, key)
            if value not in (None, ""):
                merged[key] = value

    return OPCUAConnection.from_values(
        url=str(merged["url"]),
        timeout=float(merged["timeout"]),
        session_timeout=int(merged["session_timeout"]),
        request_timeout=int(merged["request_timeout"]),
        security_mode=str(merged["security_mode"]),
        auth_policy=str(merged["auth_policy"]),
        username=str(merged["username"]),
        password=str(merged["password"]),
        cert_file=str(merged["cert_file"]),
        key_file=str(merged["key_file"]),
        server_cert=str(merged["server_cert"]),
        trust_cert=bool(merged["trust_cert"]),
    )
