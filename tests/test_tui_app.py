from __future__ import annotations

import asyncio
from types import SimpleNamespace

from asyncua import ua

from opcua_client.domain.alarm import Alarm
from opcua_client.config.runtime_config import BrowseConfig, CollectConfig, ConnectionConfig, RuntimeConfig
from opcua_client.tui.app import OpcuaTuiApp


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
