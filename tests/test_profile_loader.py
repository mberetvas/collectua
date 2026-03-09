from pathlib import Path

import pytest

from opcua_client import profile_loader


def test_list_profiles_dedup_prefers_first_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_dir = tmp_path / "repo_connections"
    user_dir = tmp_path / "user_connections"
    repo_dir.mkdir()
    user_dir.mkdir()

    (repo_dir / "prod.yaml").write_text("url: opc.tcp://repo:4840\n", encoding="utf-8")
    (user_dir / "prod.yaml").write_text("url: opc.tcp://user:4840\n", encoding="utf-8")
    (user_dir / "dev.yml").write_text("url: opc.tcp://dev:4840\n", encoding="utf-8")

    monkeypatch.setattr(profile_loader, "profile_search_dirs", lambda: [repo_dir, user_dir])

    assert profile_loader.list_profiles() == ["prod", "dev"]


def test_load_profile_reads_yaml_and_validates_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profiles_dir = tmp_path / "connections"
    profiles_dir.mkdir()
    (profiles_dir / "prod.yaml").write_text(
        "url: opc.tcp://server:4840\ntimeout: 15.0\nsecurity_mode: None_\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(profile_loader, "profile_search_dirs", lambda: [profiles_dir])

    loaded = profile_loader.load_profile("prod")

    assert loaded["url"] == "opc.tcp://server:4840"
    assert loaded["timeout"] == 15.0


def test_load_profile_raises_for_unknown_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profiles_dir = tmp_path / "connections"
    profiles_dir.mkdir()
    (profiles_dir / "prod.yaml").write_text(
        "url: opc.tcp://server:4840\nunknown_key: true\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(profile_loader, "profile_search_dirs", lambda: [profiles_dir])

    with pytest.raises(ValueError, match="unknown fields"):
        profile_loader.load_profile("prod")


def test_load_profile_raises_for_missing_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profiles_dir = tmp_path / "connections"
    profiles_dir.mkdir()

    monkeypatch.setattr(profile_loader, "profile_search_dirs", lambda: [profiles_dir])

    with pytest.raises(FileNotFoundError, match="not found"):
        profile_loader.load_profile("does-not-exist")
