from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from opcua_client import profile_loader
from opcua_client.infrastructure.config_loader import (
    load_connection_from_cli_args,
    load_connection_from_profile,
    merge_configs,
)


def test_load_connection_from_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profiles_dir = tmp_path / "connections"
    profiles_dir.mkdir()
    (profiles_dir / "plant.yaml").write_text("url: opc.tcp://plant:4840\ntimeout: 12.5\n", encoding="utf-8")
    monkeypatch.setattr(profile_loader, "profile_search_dirs", lambda: [profiles_dir])

    connection = load_connection_from_profile("plant")
    assert connection.url == "opc.tcp://plant:4840"
    assert connection.timeout == 12.5


def test_load_connection_from_cli_args() -> None:
    args = Namespace(
        command="connect",
        url="opc.tcp://cli:4840",
        timeout=20.0,
        session_timeout=60000,
        request_timeout=20000,
        username="operator",
        password="secret",
        auth_policy="Username",
        security_mode="Sign",
        cert_file="cert.pem",
        key_file="key.pem",
        server_cert="server.der",
        trust_cert=True,
        max_depth=3,
        target_namespace=[],
        csv_file="alarms.csv",
        publish_interval_ms=500,
        reconnect_delay_sec=5,
        mode="prod",
        log_level="INFO",
        debug_log_dir="logs/debug",
        logging=None,
    )
    connection = load_connection_from_cli_args(args)
    assert connection.url == "opc.tcp://cli:4840"
    assert connection.is_secure() is True


def test_merge_configs_cli_overrides_profile() -> None:
    profile = {"url": "opc.tcp://profile:4840", "timeout": 10.0}
    env_defaults = {"OPCUA_URL": "opc.tcp://env:4840", "OPCUA_TIMEOUT": 30.0}
    cli_args = Namespace(url="opc.tcp://cli:4840", timeout=22.0)

    connection = merge_configs(profile, cli_args, env_defaults)
    assert connection.url == "opc.tcp://cli:4840"
    assert connection.timeout == 22.0
