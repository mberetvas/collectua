from __future__ import annotations

import os
from pathlib import Path

import pytest

from opcua_client.config.env_defaults import clear_env_defaults_cache
from opcua_client.security.cert_paths import ensure_client_certificates, get_default_client_cert_paths


def test_default_paths_use_collectua_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Default paths should live under ~/.collectua/certs.
    """
    monkeypatch.delenv("OPCUA_ENV_FILE", raising=False)
    monkeypatch.setenv("OPCUA_CERT_BASE_DIR", str(tmp_path / ".collectua" / "certs"))
    monkeypatch.setenv("OPCUA_CLIENT_CERT_FILENAME", "myclient-selfsigned.der")
    monkeypatch.setenv("OPCUA_CLIENT_KEY_FILENAME", "myclient.pem")
    clear_env_defaults_cache()
    paths = get_default_client_cert_paths()
    assert paths.base_dir == tmp_path / ".collectua" / "certs"
    assert paths.cert_file == tmp_path / ".collectua" / "certs" / "certs" / "myclient-selfsigned.der"
    assert paths.key_file == tmp_path / ".collectua" / "certs" / "private" / "myclient.pem"
    clear_env_defaults_cache()


def test_ensure_client_certificates_creates_and_reuses(tmp_path: Path) -> None:
    """
    ensure_client_certificates should create cert/key on first call and reuse them on subsequent calls.
    """
    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        cert_path_1, key_path_1 = ensure_client_certificates()

        cert_file_1 = Path(cert_path_1)
        key_file_1 = Path(key_path_1)

        assert cert_file_1.exists()
        assert key_file_1.exists()

        cert_path_2, key_path_2 = ensure_client_certificates()

        assert cert_path_2 == cert_path_1
        assert key_path_2 == key_path_1
    finally:
        os.chdir(original_cwd)

