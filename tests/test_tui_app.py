from __future__ import annotations

import asyncio
from types import SimpleNamespace

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
