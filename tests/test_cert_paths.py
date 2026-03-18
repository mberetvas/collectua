from __future__ import annotations

import os
from pathlib import Path

from opcua_client.security.cert_paths import ensure_client_certificates, get_default_client_cert_paths


def test_default_paths_prefer_certs_under_cwd(tmp_path: Path) -> None:
    """
    When called from a given working directory, default paths should live under ./certs/.
    """
    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        paths = get_default_client_cert_paths()
        assert paths.base_dir == tmp_path / "certs"
        assert paths.cert_file == tmp_path / "certs" / "certs" / "myclient-selfsigned.der"
        assert paths.key_file == tmp_path / "certs" / "private" / "myclient.pem"
    finally:
        os.chdir(original_cwd)


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

