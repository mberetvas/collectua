from __future__ import annotations

from opcua_client.config.runtime_config import (
    BrowseConfig,
    CollectConfig,
    ConnectionConfig,
    RuntimeConfig,
)


def test_secure_mode_without_certs_does_not_fail_validation() -> None:
    """
    RuntimeConfig.validate should not require cert/key for secure modes, since
    certificates can be generated automatically at runtime.
    """
    conn = ConnectionConfig(
        url="opc.tcp://localhost:4840",
        timeout=30.0,
        auth_policy="Basic256Sha256",
        security_mode="SignAndEncrypt",
        cert_file="",
        key_file="",
    )
    runtime = RuntimeConfig(
        command="connect",
        log_level="INFO",
        connection=conn,
        browse=BrowseConfig(),
        collect=CollectConfig(),
    )

    errors = runtime.validate()

    assert "url must start with opc.tcp://" not in errors
    # No errors should mention missing cert_file/key_file for secure modes anymore.
    assert not any("cert_file is required when security_mode is not None_" in e for e in errors)
    assert not any("key_file is required when security_mode is not None_" in e for e in errors)

