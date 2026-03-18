from pathlib import Path

import pytest

from opcua_client.config import profile_loader
from opcua_client.interface import cli


def test_cli_config_uses_profile_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    profiles_dir = tmp_path / "connections"
    profiles_dir.mkdir()
    (profiles_dir / "plant.yaml").write_text(
        "url: opc.tcp://plant:4840\ntimeout: 12.5\nusername: operator\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(profile_loader, "profile_search_dirs", lambda: [profiles_dir])

    rc = cli.main(["config", "--connection-profile", "plant", "--action", "show"])
    out = capsys.readouterr().out

    assert rc == 0
    assert '"url": "opc.tcp://plant:4840"' in out
    assert '"timeout": 12.5' in out
    assert '"username": "operator"' in out


def test_cli_explicit_arg_overrides_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    profiles_dir = tmp_path / "connections"
    profiles_dir.mkdir()
    (profiles_dir / "plant.yaml").write_text(
        "url: opc.tcp://plant:4840\ntimeout: 12.5\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(profile_loader, "profile_search_dirs", lambda: [profiles_dir])

    rc = cli.main(["config", "--connection-profile", "plant", "--timeout", "99", "--action", "show"])
    out = capsys.readouterr().out

    assert rc == 0
    assert '"timeout": 99.0' in out


def test_cli_profile_not_found_returns_error(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["config", "--connection-profile", "missing", "--action", "show"])
    out = capsys.readouterr().out

    assert rc == 2
    assert "[profile error]" in out


def test_profile_loader_accepts_server_cert_and_trust_cert(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profiles_dir = tmp_path / "connections"
    profiles_dir.mkdir()
    (profiles_dir / "plant.yaml").write_text(
        "url: opc.tcp://plant:4840\n"
        "timeout: 12.5\n"
        "server_cert: plant.der\n"
        "trust_cert: true\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(profile_loader, "profile_search_dirs", lambda: [profiles_dir])

    payload = profile_loader.load_profile("plant")
    assert payload["server_cert"] == "plant.der"
    assert payload["trust_cert"] is True
