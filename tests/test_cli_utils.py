from __future__ import annotations

import asyncio
import builtins
import hashlib
from types import SimpleNamespace
from pathlib import Path

import pytest

from opcua_client.config.runtime_config import (
    BrowseConfig,
    CollectConfig,
    ConnectionConfig,
    FileLoggingConfig,
    LoggingConfig,
    RuntimeConfig,
)
from opcua_client.interface import cli


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
    import opcua_client.config.profile_loader as profile_loader_mod

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


def test_connect_smoke_uses_explicit_cert_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, object] = {}

    class DummyRoot:
        async def get_children(self) -> list[object]:
            return []

    class DummyClient:
        def __init__(self, *, url: str, timeout: float) -> None:
            created["url"] = url
            created["timeout"] = timeout
            self.application_uri = ""
            self.session_timeout = 0
            self.uaclient = SimpleNamespace(request_timeout=0)
            self.nodes = SimpleNamespace(root=DummyRoot())
            self.security_string = ""

        def set_user(self, username: str) -> None:
            created["username"] = username

        def set_password(self, password: str) -> None:
            created["password"] = password

        async def set_security_string(self, value: str) -> None:
            self.security_string = value
            created["security_string"] = value

        async def connect(self) -> None:
            return None

        async def disconnect(self) -> None:
            return None

    def fail_if_called() -> tuple[str, str]:
        raise AssertionError("ensure_client_certificates should not be called when explicit cert paths are set")

    monkeypatch.setattr(cli, "Client", DummyClient)
    monkeypatch.setattr(cli, "ensure_client_certificates", fail_if_called)

    runtime = RuntimeConfig(
        command="connect",
        log_level="INFO",
        connection=ConnectionConfig(
            url="opc.tcp://server:4840",
            timeout=5.0,
            auth_policy="Basic256Sha256",
            security_mode="Sign",
            cert_file="/tmp/from-config.der",
            key_file="/tmp/from-config.pem",
        ),
        browse=BrowseConfig(),
        collect=CollectConfig(),
    )

    asyncio.run(cli._connect_smoke(runtime))

    assert created["security_string"] == "Basic256Sha256,Sign,/tmp/from-config.der,/tmp/from-config.pem"


def test_connect_smoke_patches_server_uri_from_discovered_application_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class DummyRoot:
        async def get_children(self) -> list[object]:
            return []

    class DummyClient:
        def __init__(self, *, url: str, timeout: float) -> None:
            self.application_uri = ""
            self.session_timeout = 0
            self.uaclient = SimpleNamespace(request_timeout=0)
            self.uaclient.create_session = self._create_session
            self.nodes = SimpleNamespace(root=DummyRoot())

        async def _create_session(self, parameters) -> str:
            captured["server_uri"] = parameters.ServerUri
            return "ok"

        def set_user(self, username: str) -> None:
            return None

        def set_password(self, password: str) -> None:
            return None

        async def set_security_string(self, value: str) -> None:
            return None

        async def connect_and_get_server_endpoints(self) -> list[object]:
            return [
                SimpleNamespace(
                    SecurityPolicyUri="http://opcfoundation.org/UA/SecurityPolicy#Basic256Sha256",
                    SecurityMode=SimpleNamespace(name="Sign"),
                    Server=SimpleNamespace(ApplicationUri="urn:OpcPlc:container123"),
                )
            ]

        async def connect(self) -> None:
            params = SimpleNamespace(ServerUri="urn:localhost")
            await self.uaclient.create_session(params)

        async def disconnect(self) -> None:
            return None

    monkeypatch.setattr(cli, "Client", DummyClient)
    monkeypatch.setattr(cli, "ensure_client_certificates", lambda: ("client.der", "client.pem"))

    runtime = RuntimeConfig(
        command="connect",
        log_level="INFO",
        connection=ConnectionConfig(
            url="opc.tcp://server:4840",
            timeout=5.0,
            auth_policy="Basic256Sha256",
            security_mode="Sign",
        ),
        browse=BrowseConfig(),
        collect=CollectConfig(),
    )

    asyncio.run(cli._connect_smoke(runtime))

    assert captured["server_uri"] == "urn:OpcPlc:container123"


def test_connect_smoke_skips_server_uri_patch_when_discovery_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class DummyRoot:
        async def get_children(self) -> list[object]:
            return []

    class DummyClient:
        def __init__(self, *, url: str, timeout: float) -> None:
            self.application_uri = ""
            self.session_timeout = 0
            self.uaclient = SimpleNamespace(request_timeout=0)
            self.uaclient.create_session = self._create_session
            self.nodes = SimpleNamespace(root=DummyRoot())

        async def _create_session(self, parameters) -> str:
            captured["server_uri"] = parameters.ServerUri
            return "ok"

        def set_user(self, username: str) -> None:
            return None

        def set_password(self, password: str) -> None:
            return None

        async def set_security_string(self, value: str) -> None:
            return None

        async def connect_and_get_server_endpoints(self) -> list[object]:
            raise RuntimeError("discovery unavailable")

        async def connect(self) -> None:
            params = SimpleNamespace(ServerUri="urn:localhost")
            await self.uaclient.create_session(params)

        async def disconnect(self) -> None:
            return None

    monkeypatch.setattr(cli, "Client", DummyClient)
    monkeypatch.setattr(cli, "ensure_client_certificates", lambda: ("client.der", "client.pem"))

    runtime = RuntimeConfig(
        command="connect",
        log_level="INFO",
        connection=ConnectionConfig(
            url="opc.tcp://server:4840",
            timeout=5.0,
            auth_policy="Basic256Sha256",
            security_mode="Sign",
        ),
        browse=BrowseConfig(),
        collect=CollectConfig(),
    )

    asyncio.run(cli._connect_smoke(runtime))

    assert captured["server_uri"] == "urn:localhost"
