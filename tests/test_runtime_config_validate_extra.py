from __future__ import annotations

from opcua_client.runtime_config import (
    BrowseConfig,
    CollectConfig,
    ConnectionConfig,
    FileLoggingConfig,
    LoggingConfig,
    RuntimeConfig,
)


def _make_base_runtime() -> RuntimeConfig:
    conn = ConnectionConfig(url="opc.tcp://server:4840", timeout=30.0)
    browse_cfg = BrowseConfig()
    collect_cfg = CollectConfig()
    return RuntimeConfig(
        command="connect",
        log_level="INFO",
        connection=conn,
        browse=browse_cfg,
        collect=collect_cfg,
        mode="prod",
        debug_log_dir="logs/debug",
    )


def test_validate_url_scheme() -> None:
    cfg = _make_base_runtime()
    cfg.connection.url = "http://not-opc"

    errors = cfg.validate()

    assert "url must start with opc.tcp://" in errors


def test_validate_timeouts_must_be_positive() -> None:
    cfg = _make_base_runtime()
    cfg.connection.timeout = 0
    cfg.connection.session_timeout = 0
    cfg.connection.request_timeout = -1

    errors = cfg.validate()

    assert "timeout must be greater than 0" in errors
    assert "session_timeout must be greater than 0" in errors
    assert "request_timeout must be greater than 0" in errors


def test_validate_browse_and_collect_constraints() -> None:
    cfg = _make_base_runtime()
    cfg.browse.max_depth = -1
    cfg.browse.target_namespaces = [0, -5]
    cfg.collect.publish_interval_ms = 0
    cfg.collect.reconnect_delay_sec = -1

    errors = cfg.validate()

    assert "max_depth must be >= 0" in errors
    assert "target_namespace values must be >= 0" in errors
    assert "publish_interval_ms must be greater than 0" in errors
    assert "reconnect_delay_sec must be >= 0" in errors


def test_validate_ok_for_valid_configuration() -> None:
    cfg = _make_base_runtime()
    cfg.browse.max_depth = 2
    cfg.browse.target_namespaces = [0, 2]
    cfg.collect.publish_interval_ms = 100
    cfg.collect.reconnect_delay_sec = 1

    assert cfg.validate() == []


def test_logging_config_dataclasses_shape() -> None:
    file_cfg = FileLoggingConfig(
        enabled=True,
        path="logs/custom",
        name_pattern="custom-{timestamp}-pid{pid}.log",
    )
    logging_cfg = LoggingConfig(level="DEBUG", file=file_cfg)
    conn = ConnectionConfig(
        url="opc.tcp://server:4840",
        timeout=30.0,
        logging_config=logging_cfg,
    )

    runtime = RuntimeConfig(
        command="collect",
        log_level="DEBUG",
        connection=conn,
        browse=BrowseConfig(),
        collect=CollectConfig(),
        mode="debug",
        debug_log_dir="logs/debug",
    )

    # Sanity check: the dataclasses round-trip through as_dict/as_json without errors.
    data = runtime.as_dict(mask_sensitive=True)
    assert data["connection"]["logging_config"]["file"]["enabled"] is True
    assert "custom-" in data["connection"]["logging_config"]["file"]["name_pattern"]

    json_str = runtime.as_json(mask_sensitive=True)
    assert '"logging_config"' in json_str

