from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from opcua_client.config import profile_loader
from opcua_client.config.env_defaults import clear_env_defaults_cache
from opcua_client.config.runtime_config import RuntimeConfig
from opcua_client.security.cert_paths import get_default_client_cert_paths


def test_runtime_config_from_namespace_uses_env_defaults(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPCUA_URL=opc.tcp://env-default:4840",
                "OPCUA_TIMEOUT=12.5",
                "OPCUA_SESSION_TIMEOUT=45000",
                "OPCUA_REQUEST_TIMEOUT=15000",
                "OPCUA_LOG_LEVEL=WARNING",
                "OPCUA_MODE=debug",
                "OPCUA_DEBUG_LOG_DIR=logs/from-env",
                "OPCUA_MAX_DEPTH=7",
                "OPCUA_TARGET_NAMESPACES=2,4",
                "OPCUA_CSV_FILE=env-alarms.csv",
                "OPCUA_PUBLISH_INTERVAL_MS=750",
                "OPCUA_RECONNECT_DELAY_SEC=11",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("OPCUA_ENV_FILE", str(env_file))
    clear_env_defaults_cache()

    config = RuntimeConfig.from_namespace(Namespace(command="config"))

    assert config.connection.url == "opc.tcp://env-default:4840"
    assert config.connection.timeout == 12.5
    assert config.connection.session_timeout == 45000
    assert config.connection.request_timeout == 15000
    assert config.log_level == "WARNING"
    assert config.mode == "debug"
    assert config.debug_log_dir == "logs/from-env"
    assert config.browse.max_depth == 7
    assert config.browse.target_namespaces == [2, 4]
    assert config.collect.csv_file == "env-alarms.csv"
    assert config.collect.publish_interval_ms == 750
    assert config.collect.reconnect_delay_sec == 11

    clear_env_defaults_cache()


def test_profile_search_dirs_use_env_overrides(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPCUA_PROFILE_DIR=custom-profiles",
                "OPCUA_FALLBACK_PROFILE_DIR=~/opcua-test-profiles",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("OPCUA_ENV_FILE", str(env_file))
    monkeypatch.chdir(tmp_path)
    clear_env_defaults_cache()

    search_dirs = profile_loader.profile_search_dirs()

    assert search_dirs[0] == tmp_path / "custom-profiles"
    assert search_dirs[1] == Path("~/opcua-test-profiles").expanduser()

    clear_env_defaults_cache()


def test_cert_paths_use_env_overrides(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPCUA_CERT_BASE_DIR=custom-certs",
                "OPCUA_CLIENT_CERT_FILENAME=client-env.der",
                "OPCUA_CLIENT_KEY_FILENAME=client-env.pem",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("OPCUA_ENV_FILE", str(env_file))
    monkeypatch.chdir(tmp_path)
    clear_env_defaults_cache()

    paths = get_default_client_cert_paths()

    assert paths.base_dir == tmp_path / "custom-certs"
    assert paths.cert_file == tmp_path / "custom-certs" / "certs" / "client-env.der"
    assert paths.key_file == tmp_path / "custom-certs" / "private" / "client-env.pem"

    clear_env_defaults_cache()
