from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

from asyncua import ua
from rich.text import Text

from opcua_client.domain.alarm import Alarm
from opcua_client.config.runtime_config import BrowseConfig, CollectConfig, ConnectionConfig, RuntimeConfig
from opcua_client.tui.app import OpcuaTuiApp
from opcua_client.tui.widgets.log_stream import LogStreamWidget, SqliteLogRow


def test_create_client_normalizes_string_auth_policy(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class DummyClient:
        def __init__(self, *, url: str, timeout: float) -> None:
            self.url = url
            self.timeout = timeout
            self.application_uri = ""
            self.session_timeout = 0
            self.uaclient = SimpleNamespace(request_timeout=0, create_session=None)

        def set_user(self, username: str) -> None:
            return None

        def set_password(self, password: str) -> None:
            return None

        async def set_security_string(self, value: str) -> None:
            captured["security_string"] = value

        async def connect_and_get_server_endpoints(self) -> list[object]:
            return [
                SimpleNamespace(
                    SecurityPolicyUri="http://opcfoundation.org/UA/SecurityPolicy#Aes128_Sha256_RsaOaep",
                    SecurityMode=SimpleNamespace(name="Sign"),
                    Server=SimpleNamespace(ApplicationUri="urn:OpcPlc:container123"),
                )
            ]

    monkeypatch.setattr("opcua_client.tui.app.Client", DummyClient)
    monkeypatch.setattr("opcua_client.tui.app.ensure_client_certificates", lambda: ("client.der", "client.pem"))

    config = RuntimeConfig(
        command="tui",
        connection=ConnectionConfig(
            url="opc.tcp://localhost:50000",
            timeout=5.0,
            auth_policy="Aes128_Sha256_RsaOaep",
            security_mode="Sign",
        ),
        browse=BrowseConfig(),
        collect=CollectConfig(),
    )

    app = OpcuaTuiApp(config)

    asyncio.run(app._create_client())

    assert captured["security_string"] == "Aes128Sha256RsaOaep,Sign,client.der,client.pem"


def test_create_client_does_not_patch_create_session(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self, *, url: str, timeout: float) -> None:
            self.application_uri = ""
            self.session_timeout = 0
            self.uaclient = SimpleNamespace(request_timeout=0)
            self.uaclient.create_session = self._create_session

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
                    SecurityPolicyUri="http://opcfoundation.org/UA/SecurityPolicy#Aes128_Sha256_RsaOaep",
                    SecurityMode=SimpleNamespace(name="Sign"),
                    Server=SimpleNamespace(ApplicationUri="urn:OpcPlc:container123"),
                )
            ]

    monkeypatch.setattr("opcua_client.tui.app.Client", DummyClient)
    monkeypatch.setattr("opcua_client.tui.app.ensure_client_certificates", lambda: ("client.der", "client.pem"))

    config = RuntimeConfig(
        command="tui",
        connection=ConnectionConfig(
            url="opc.tcp://localhost:50000",
            timeout=5.0,
            auth_policy="Aes128_Sha256_RsaOaep",
            security_mode="Sign",
        ),
        browse=BrowseConfig(),
        collect=CollectConfig(),
    )

    app = OpcuaTuiApp(config)
    client = asyncio.run(app._create_client())
    params = SimpleNamespace(ServerUri="urn:localhost")
    result = asyncio.run(client.uaclient.create_session(params))

    assert result == "ok"
    assert captured["server_uri"] == "urn:OpcPlc:container123"


def test_create_client_skips_patch_when_endpoint_discovery_fails(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self, *, url: str, timeout: float) -> None:
            self.application_uri = ""
            self.session_timeout = 0
            self.uaclient = SimpleNamespace(request_timeout=0)
            self.uaclient.create_session = self._create_session

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

    monkeypatch.setattr("opcua_client.tui.app.Client", DummyClient)
    monkeypatch.setattr("opcua_client.tui.app.ensure_client_certificates", lambda: ("client.der", "client.pem"))

    config = RuntimeConfig(
        command="tui",
        connection=ConnectionConfig(
            url="opc.tcp://localhost:50000",
            timeout=5.0,
            auth_policy="Aes128_Sha256_RsaOaep",
            security_mode="Sign",
        ),
        browse=BrowseConfig(),
        collect=CollectConfig(),
    )

    app = OpcuaTuiApp(config)
    client = asyncio.run(app._create_client())
    params = SimpleNamespace(ServerUri="urn:localhost")
    result = asyncio.run(client.uaclient.create_session(params))

    assert result == "ok"
    assert captured["server_uri"] == "urn:localhost"


def test_create_client_applies_locales(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self, *, url: str, timeout: float) -> None:
            self.application_uri = ""
            self.session_timeout = 0
            self.uaclient = SimpleNamespace(request_timeout=0)

        def set_user(self, username: str) -> None:
            return None

        def set_password(self, password: str) -> None:
            return None

    monkeypatch.setattr("opcua_client.tui.app.Client", DummyClient)

    config = RuntimeConfig(
        command="tui",
        connection=ConnectionConfig(
            url="opc.tcp://localhost:50000",
            timeout=5.0,
            locales=["en-US", "de-DE"],
        ),
        browse=BrowseConfig(),
        collect=CollectConfig(),
    )

    app = OpcuaTuiApp(config)
    client = asyncio.run(app._create_client())

    captured["locale"] = getattr(client, "_locale", None)
    captured["session_locale_ids"] = getattr(client, "session_locale_ids", None)

    assert captured["locale"] == ["en-US", "de-DE"]
    assert captured["session_locale_ids"] == ["en-US", "de-DE"]


def test_read_selected_node_value_handles_goodoverload(monkeypatch) -> None:
    class DummyPanel:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def display_node(self, node_data, *, value_text=None, value_status=None) -> None:
            self.calls.append(
                {
                    "node_data": node_data,
                    "value_text": value_text,
                    "value_status": value_status,
                }
            )

    class DummyNode:
        async def read_data_value(self):
            return SimpleNamespace(
                StatusCode=ua.StatusCode(ua.StatusCodes.GoodOverload),
                Value=SimpleNamespace(Value=123),
            )

    class DummyClient:
        def get_node(self, node_id: str) -> DummyNode:
            assert node_id == "ns=2;s=Tag1"
            return DummyNode()

    config = RuntimeConfig(
        command="tui",
        connection=ConnectionConfig(url="opc.tcp://localhost:50000", timeout=5.0),
        browse=BrowseConfig(),
        collect=CollectConfig(),
    )
    app = OpcuaTuiApp(config)
    panel = DummyPanel()
    node_data = {"id": "ns=2;s=Tag1", "cls": "Variable", "name": "Tag1"}

    app._client = DummyClient()
    app._selected_node = node_data
    monkeypatch.setattr(app, "query_one", lambda selector: panel)

    asyncio.run(app._read_selected_node_value(node_data))

    assert panel.calls
    assert "PLC Busy: GoodOverload" in str(panel.calls[-1]["value_text"])


def test_action_acknowledge_selected_alarm_schedules_ack(monkeypatch) -> None:
    alarm = Alarm.from_values(
        alarm_id="ns=2;s=alarm-1",
        condition_name="Overheat",
        source_name="Motor1",
        message="Too hot",
        severity=500,
        timestamp_utc="2024-01-01T00:00:00Z",
        event_id="0102",
        event_id_bytes=b"\x01\x02",
    )

    class DummyTable:
        has_focus = True

        def get_selected_alarm(self) -> Alarm:
            return alarm

    config = RuntimeConfig(
        command="tui",
        connection=ConnectionConfig(url="opc.tcp://localhost:50000", timeout=5.0),
        browse=BrowseConfig(),
        collect=CollectConfig(),
    )
    app = OpcuaTuiApp(config)
    app._client = object()

    notices: list[str] = []
    monkeypatch.setattr(app, "notify", lambda message, timeout=0.0: notices.append(message))
    monkeypatch.setattr(app, "query_one", lambda selector: DummyTable())

    captured: dict[str, Alarm] = {}

    async def fake_ack_task(selected_alarm: Alarm) -> None:
        captured["alarm"] = selected_alarm

    monkeypatch.setattr(app, "_acknowledge_alarm_task", fake_ack_task)

    async def _exercise() -> None:
        app.action_acknowledge_selected_alarm()
        await asyncio.sleep(0)

    asyncio.run(_exercise())

    assert captured["alarm"] is alarm
    assert notices[0].startswith("Acknowledging Overheat")


def test_load_all_logs_uses_fetch_recent_without_reformatting(monkeypatch) -> None:
    class DummyHandler:
        def __init__(self, rows: list[SqliteLogRow]) -> None:
            self.rows = rows
            self.calls: list[int] = []

        def fetch_recent(self, limit: int = 1000) -> list[SqliteLogRow]:
            self.calls.append(limit)
            return self.rows

    class DummyLogStream:
        def __init__(self) -> None:
            self.cleared = False
            self.entries: list[tuple[int, str]] = []

        def clear(self) -> None:
            self.cleared = True

        def add_entry(self, entry, levelno: int = logging.NOTSET) -> None:
            self.entries.append((levelno, entry.plain))

    config = RuntimeConfig(
        command="tui",
        connection=ConnectionConfig(url="opc.tcp://localhost:50000", timeout=5.0),
        browse=BrowseConfig(),
        collect=CollectConfig(),
    )
    app = OpcuaTuiApp(config)
    rows = [
        SqliteLogRow(
            id=8,
            timestamp_utc="2026-03-19T10:10:11+00:00",
            levelno=logging.ERROR,
            levelname="ERROR",
            logger_name="beta",
            message="2026-03-19T10:10:11 ERROR beta: already formatted two",
        ),
        SqliteLogRow(
            id=7,
            timestamp_utc="2026-03-19T10:10:10+00:00",
            levelno=logging.INFO,
            levelname="INFO",
            logger_name="alpha",
            message="2026-03-19T10:10:10 INFO alpha: already formatted one",
        ),
    ]
    handler = DummyHandler(rows)
    log_stream = DummyLogStream()
    app._log_handler = handler
    monkeypatch.setattr(app, "query_one", lambda selector: log_stream)

    import asyncio
    asyncio.run(app._load_all_logs_async())

    assert handler.calls == [1000]
    assert log_stream.cleared
    assert [text for _, text in log_stream.entries] == [row.message for row in reversed(rows)]
    assert app._last_log_row_id == rows[0].id


def test_action_copy_warnings_copies_exact_warning_level(monkeypatch) -> None:
    class DummyLogStream:
        def __init__(self) -> None:
            self.calls: list[tuple[int, int | None]] = []

        def export_text(
            self, min_level: int = logging.NOTSET, exact_level: int | None = None
        ) -> str:
            self.calls.append((min_level, exact_level))
            if exact_level == logging.WARNING:
                return "warn-one\nwarn-two\n"
            return ""

    config = RuntimeConfig(
        command="tui",
        connection=ConnectionConfig(url="opc.tcp://localhost:50000", timeout=5.0),
        browse=BrowseConfig(),
        collect=CollectConfig(),
    )
    app = OpcuaTuiApp(config)
    log_stream = DummyLogStream()
    clipboard: list[str] = []
    notices: list[str] = []

    monkeypatch.setattr(app, "query_one", lambda selector: log_stream)
    monkeypatch.setattr(app, "_copy_to_clipboard_robust", lambda text: clipboard.append(text))
    monkeypatch.setattr(app, "notify", lambda message, timeout=0.0: notices.append(message))

    app.action_copy_warnings()

    assert log_stream.calls == [(logging.NOTSET, logging.WARNING)]
    assert clipboard == ["warn-one\nwarn-two\n"]
    assert notices == ["Copied warning logs to clipboard."]


def test_action_copy_warnings_notifies_when_no_warnings(monkeypatch) -> None:
    class DummyLogStream:
        def export_text(
            self, min_level: int = logging.NOTSET, exact_level: int | None = None
        ) -> str:
            return ""

    config = RuntimeConfig(
        command="tui",
        connection=ConnectionConfig(url="opc.tcp://localhost:50000", timeout=5.0),
        browse=BrowseConfig(),
        collect=CollectConfig(),
    )
    app = OpcuaTuiApp(config)
    clipboard: list[str] = []
    notices: list[str] = []

    monkeypatch.setattr(app, "query_one", lambda selector: DummyLogStream())
    monkeypatch.setattr(app, "_copy_to_clipboard_robust", lambda text: clipboard.append(text))
    monkeypatch.setattr(app, "notify", lambda message, timeout=0.0: notices.append(message))

    app.action_copy_warnings()

    assert clipboard == []
    assert notices == ["No warnings to copy yet."]


def test_log_stream_export_text_exact_warning_preserves_panel_order() -> None:
    log_stream = LogStreamWidget()
    log_stream._entries = [
        (logging.INFO, Text("info-oldest")),
        (logging.WARNING, Text("warn-older")),
        (logging.ERROR, Text("error-middle")),
        (logging.WARNING, Text("warn-newest")),
    ]

    exported = log_stream.export_text(exact_level=logging.WARNING)

    assert exported == "warn-newest\nwarn-older\n"
