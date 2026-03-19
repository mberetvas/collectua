import builtins
from pathlib import Path

import pytest

from opcua_client.config import profile_autosetup, profile_loader


def test_generate_suggested_name_uses_host_and_port() -> None:
    url = "opc.tcp://example-host:4840"
    suggested = profile_autosetup._generate_suggested_name(url)
    assert suggested == "example-host:4840"


def test_prompt_friendly_name_allows_empty_to_skip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No existing profiles.
    monkeypatch.setattr(profile_loader, "profile_search_dirs", lambda: [])
    monkeypatch.setattr(builtins, "input", lambda *args, **kwargs: "")

    result = profile_autosetup._prompt_friendly_name("opc.tcp://example-host:4840")
    assert result == ""


def test_prompt_friendly_name_rejects_path_separators_and_uses_second_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # No existing profiles, but ensure that invalid characters are rejected.
    monkeypatch.setattr(profile_loader, "profile_search_dirs", lambda: [])

    inputs = iter(["bad/name", "good-name"])

    def _fake_input(prompt: str = "") -> str:  # type: ignore[override]
        return next(inputs)

    monkeypatch.setattr(builtins, "input", _fake_input)

    result = profile_autosetup._prompt_friendly_name("opc.tcp://example-host:4840")

    out = capsys.readouterr().out
    assert "must not contain '/' or '\\'" in out
    assert result == "good-name"


def test_prompt_friendly_name_detects_duplicate_and_allows_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Prepare an existing profile that already uses a given friendly name.
    profiles_dir = tmp_path / "connections"
    profiles_dir.mkdir()
    (profiles_dir / "existing.yaml").write_text(
        "url: opc.tcp://existing:4840\n"
        "friendly_name: Duplicate Name\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        profile_loader, "profile_search_dirs", lambda: [profiles_dir]
    )

    # First input: proposed duplicate name.
    # Second input: confirmation 'y' to reuse the duplicate name.
    inputs = iter(["Duplicate Name", "y"])

    def _fake_input(prompt: str = "") -> str:  # type: ignore[override]
        return next(inputs)

    monkeypatch.setattr(builtins, "input", _fake_input)

    result = profile_autosetup._prompt_friendly_name("opc.tcp://other:4840")
    assert result == "Duplicate Name"

