from __future__ import annotations

import pytest

from opcua_client.domain.connection import AuthPolicy, Credentials, OPCUAConnection, SecurityMode
from opcua_client.domain.exceptions import ConnectionValidationError, InvalidOPCUAUrl, InvalidSecurityMode


def test_security_mode_parsing() -> None:
    assert SecurityMode.from_value("None_") == SecurityMode.NONE
    assert SecurityMode.from_value("Sign") == SecurityMode.SIGN
    assert SecurityMode.from_value("SignAndEncrypt") == SecurityMode.SIGN_AND_ENCRYPT


def test_security_mode_invalid_raises() -> None:
    with pytest.raises(InvalidSecurityMode):
        SecurityMode.from_value("invalid")


def test_connection_url_validation() -> None:
    with pytest.raises(InvalidOPCUAUrl):
        OPCUAConnection.from_values(url="http://wrong")


def test_connection_timeout_validation() -> None:
    with pytest.raises(ConnectionValidationError):
        OPCUAConnection.from_values(url="opc.tcp://server:4840", timeout=0)


def test_connection_helpers_and_credentials() -> None:
    connection = OPCUAConnection.from_values(
        url="opc.tcp://server:4840",
        security_mode="Sign",
        auth_policy="Basic256Sha256",
        username="operator",
        password="secret",
        cert_file="cert.pem",
        key_file="key.pem",
    )
    assert connection.is_secure() is True
    assert connection.requires_client_cert() is True
    assert isinstance(connection.credentials, Credentials)
    assert connection.credentials.is_username_auth() is True
    assert connection.auth_policy == AuthPolicy.BASIC256SHA256
