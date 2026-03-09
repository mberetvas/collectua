import pytest

from opcua_client import tui


class _DummyApp:
    def __init__(self, config):
        self.config = config

    def run(self) -> None:
        return None


def test_tui_no_args_no_profiles_shows_guidance(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(tui, "list_profiles", lambda: [])

    rc = tui.main([])
    out = capsys.readouterr().out

    assert rc == 2
    assert "No connection profiles available" in out


def test_tui_no_args_prompts_and_uses_selected_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tui, "list_profiles", lambda: ["prod"])
    monkeypatch.setattr(tui, "_choose_profile_name", lambda profiles: "prod")
    monkeypatch.setattr(
        tui,
        "load_profile",
        lambda name: {
            "url": "opc.tcp://from-profile:4840",
            "timeout": 22.0,
        },
    )

    captured: dict[str, object] = {}

    class CapturingApp(_DummyApp):
        def __init__(self, config):
            super().__init__(config)
            captured["url"] = config.connection.url
            captured["timeout"] = config.connection.timeout

    monkeypatch.setattr(tui, "OpcuaTuiApp", CapturingApp)

    rc = tui.main([])

    assert rc == 0
    assert captured["url"] == "opc.tcp://from-profile:4840"
    assert captured["timeout"] == 22.0


def test_tui_explicit_url_keeps_normal_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tui, "OpcuaTuiApp", _DummyApp)

    rc = tui.main(["--url", "opc.tcp://direct:4840"])

    assert rc == 0
