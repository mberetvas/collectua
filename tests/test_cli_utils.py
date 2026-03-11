from __future__ import annotations

import asyncio
import builtins
import hashlib
from pathlib import Path

import pytest

from opcua_client import cli
from opcua_client.runtime_config import (
    BrowseConfig,
    CollectConfig,
    ConnectionConfig,
    FileLoggingConfig,
    LoggingConfig,
    RuntimeConfig,
)


def test_short_policy_from_uri_empty_and_plain() -> None:
    assert cli._short_policy_from_uri("") == "None"
    assert cli._short_policy_from_uri("Basic256Sha256") == "Basic256Sha256"


def test_short_policy_from_uri_full_uri_and_malformed() -> None:
    uri = "http://opcfoundation.org/UA/SecurityPolicy#Basic256Sha256"
    assert cli._short_policy_from_uri(uri) == "Basic256Sha256"

    # Trailing '#' should fall back to 'None'
    assert cli._short_policy_from_uri("http://example/#") == "None"


def test_format_cert_fingerprint_basic() -> None:
    data = b"\x01\x23\x45\x67\x89\xab\xcd\xef"
    # _format_cert_fingerprint uses SHA256 of the input bytes.
    expected = hashlib.sha256(data).hexdigest()
    expected = ":".join(expected[i : i + 2] for i in range(0, len(expected), 2))
    fp = cli._format_cert_fingerprint(data)
    assert fp == expected


def test_format_cert_fingerprint_empty() -> None:
    data = b""
    expected = hashlib.sha256(data).hexdigest()
    expected = ":".join(expected[i : i + 2] for i in range(0, len(expected), 2))
    assert cli._format_cert_fingerprint(data) == expected


def _make_runtime_with_logging(
    *,
    mode: str = "prod",
    log_level: str = "INFO",
    console_level: str | None = None,
    file_enabled: bool = False,
    file_path: Path | None = None,
    file_pattern: str = "debug-{timestamp}-pid{pid}.log",
) -> tuple[RuntimeConfig, ConnectionConfig]:
    file_cfg = FileLoggingConfig(
        enabled=file_enabled,
        path=str(file_path) if file_path is not None else "logs/debug",
        name_pattern=file_pattern,
    )
    logging_cfg = LoggingConfig(
        level=console_level or log_level,
        file=file_cfg,
    )
    conn = ConnectionConfig(
        url="opc.tcp://example:4840",
        timeout=30.0,
        logging_config=logging_cfg,
    )
    runtime = RuntimeConfig(
        command="collect",
        log_level=log_level,
        connection=conn,
        browse=BrowseConfig(),
        collect=CollectConfig(),
        mode=mode,
        debug_log_dir="logs/debug",
    )
    return runtime, conn


def test_configure_logging_debug_mode_writes_file(tmp_path: Path) -> None:
    from logging import getLogger

    debug_dir = tmp_path / "debug-logs"
    debug_dir.mkdir()

    # Use mode='debug' without per-connection logging config to force file handler.
    log_file = cli._configure_logging(
        mode="debug",
        log_level="INFO",
        debug_log_dir=str(debug_dir),
        connection_config=None,
    )

    assert log_file is not None
    path = Path(log_file)
    assert path.is_file()
    assert path.parent == debug_dir

    # Write one log line to force file output, then flush handlers.
    root = getLogger()
    root.info("debug-mode-file-test")
    for handler in root.handlers:
        flush = getattr(handler, "flush", None)
        if callable(flush):
            flush()

    # File should now contain at least one formatted log line.
    assert path.stat().st_size > 0


def test_configure_logging_uses_connection_logging_config(tmp_path: Path) -> None:
    from logging import getLogger

    log_dir = tmp_path / "logs"
    runtime, conn = _make_runtime_with_logging(
        mode="prod",
        log_level="DEBUG",
        console_level="WARNING",
        file_enabled=True,
        file_path=log_dir,
        file_pattern="custom-{timestamp}-pid{pid}.log",
    )

    log_file = cli._configure_logging(
        mode=runtime.mode,
        log_level=runtime.log_level,
        debug_log_dir=runtime.debug_log_dir,
        connection_config=conn,
    )

    assert log_file is not None
    path = Path(log_file)
    assert path.parent == log_dir
    assert path.name.startswith("custom-")
    assert "pid" in path.name

    # Root logger should have a handler with DEBUG level (since file logging is enabled).
    root = getLogger()
    assert any(h.level == 10 for h in root.handlers)  # 10 == logging.DEBUG


def test_persist_trust_to_profile_updates_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profile_path = tmp_path / "plant.yaml"
    profile_path.write_text("url: opc.tcp://server:4840\n", encoding="utf-8")

    class DummyLoader:
        def __init__(self, data: dict[str, object]) -> None:
            self.data = data

        def load_profile(self, name: str) -> dict[str, object]:
            assert name == "plant"
            return dict(self.data)

    dummy_loader = DummyLoader({"url": "opc.tcp://server:4840"})

    # Monkeypatch opcua_client.profile_loader (imported inside _persist_trust_to_profile)
    import opcua_client.profile_loader as profile_loader_mod

    monkeypatch.setattr(profile_loader_mod, "load_profile", dummy_loader.load_profile)
    monkeypatch.setattr(cli, "resolve_profile_path", lambda name: profile_path)

    cert_path = tmp_path / "plant.der"

    cli._persist_trust_to_profile("plant", cert_path)

    content = profile_path.read_text(encoding="utf-8")
    assert "server_cert: " in content
    assert "trust_cert: true" in content


def test_ensure_server_trust_skips_insecure_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = ConnectionConfig(
        url="opc.tcp://server:4840",
        timeout=30.0,
        security_mode="None_",
    )
    runtime = RuntimeConfig(
        command="connect",
        log_level="INFO",
        connection=conn,
        browse=BrowseConfig(),
        collect=CollectConfig(),
        mode="prod",
        debug_log_dir="logs/debug",
    )

    called = False

    async def fake_collect(config: RuntimeConfig) -> bytes:  # pragma: no cover - trivial
        nonlocal called
        called = True
        return b""

    monkeypatch.setattr(cli, "_collect_server_certificate", fake_collect)

    asyncio.run(cli._ensure_server_trust(runtime, profile_name=None))

    # In insecure mode we must not even attempt to collect server certs.
    assert called is False


def test_ensure_server_trust_user_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = ConnectionConfig(
        url="opc.tcp://server:4840",
        timeout=30.0,
        security_mode="Sign",
        trust_cert=False,
    )
    runtime = RuntimeConfig(
        command="connect",
        log_level="INFO",
        connection=conn,
        browse=BrowseConfig(),
        collect=CollectConfig(),
        mode="prod",
        debug_log_dir="logs/debug",
    )

    async def fake_collect(config: RuntimeConfig) -> bytes:
        return b"abc"

    monkeypatch.setattr(cli, "_collect_server_certificate", fake_collect)
    monkeypatch.setattr(cli, "_format_cert_fingerprint", lambda b: "FF:FF")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    # Simulate user typing 'n' followed by newline.
    def fake_input(prompt: str) -> str:
        return "n"

    monkeypatch.setattr(builtins, "input", fake_input)

    with pytest.raises(RuntimeError, match="not trusted"):
        asyncio.run(cli._ensure_server_trust(runtime, profile_name=None))

    assert conn.trust_cert is False


def test_ensure_server_trust_user_accepts_and_persists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = ConnectionConfig(
        url="opc.tcp://server:4840",
        timeout=30.0,
        security_mode="Sign",
        trust_cert=False,
    )
    runtime = RuntimeConfig(
        command="connect",
        log_level="INFO",
        connection=conn,
        browse=BrowseConfig(),
        collect=CollectConfig(),
        mode="prod",
        debug_log_dir="logs/debug",
    )

    async def fake_collect(config: RuntimeConfig) -> bytes:
        return b"\x00\x01"

    monkeypatch.setattr(cli, "_collect_server_certificate", fake_collect)
    monkeypatch.setattr(cli, "_format_cert_fingerprint", lambda b: "AA:BB")

    profile_path = tmp_path / "plant.yaml"
    profile_path.write_text("url: opc.tcp://server:4840\n", encoding="utf-8")
    monkeypatch.setattr(cli, "resolve_profile_path", lambda name: profile_path)

    persisted: dict[str, object] = {}

    def fake_persist(profile_name: str, server_cert_path: Path) -> None:
        persisted["name"] = profile_name
        persisted["path"] = server_cert_path

    monkeypatch.setattr(cli, "_persist_trust_to_profile", fake_persist)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda prompt: "y")

    asyncio.run(cli._ensure_server_trust(runtime, profile_name="plant"))

    assert conn.trust_cert is True
    assert persisted["name"] == "plant"
    assert isinstance(persisted["path"], Path)
    # Cert file should have been written.
    assert persisted["path"].is_file()

