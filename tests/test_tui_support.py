from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

from opcua_client.tui.app import (
    AlarmRow,
    HelpScreen,
    StartupSplashScreen,
    TuiAlarmHandler,
)


def test_help_screen_compose_yields_single_static() -> None:
    screen = HelpScreen()
    children = list(screen.compose())
    # HelpScreen.compose should yield exactly one child (Static help widget).
    assert len(children) == 1


def test_startup_splash_read_ascii_lines_uses_file(tmp_path: Path) -> None:
    art = tmp_path / "art.txt"
    art.write_text("line1\nline2  \n", encoding="utf-8")

    screen = StartupSplashScreen(art)
    lines = screen._read_ascii_lines()

    assert lines == ["line1", "line2"]


def test_startup_splash_read_ascii_lines_fallback(tmp_path: Path) -> None:
    art = tmp_path / "missing.txt"
    screen = StartupSplashScreen(art)
    lines = screen._read_ascii_lines()

    # Falls back to built-in banner.
    assert "OPC UA Command Center" in lines


@dataclass
class _DummyApp:
    messages: List[Any]

    def post_message(self, message: Any) -> None:
        self.messages.append(message)


class _DummyNodeId:
    def __init__(self, s: str) -> None:
        self._s = s

    def to_string(self) -> str:
        return self._s


class _DummyState:
    def __init__(self, value: Any) -> None:
        self.Id = value


class _DummyEvent:
    def __init__(
        self,
        *,
        condition_id: Any | None = None,
        retain: Any | None = None,
        active_state: Any | None = None,
        acked_state: Any | None = None,
    ) -> None:
        self.Time = "2024-01-01T00:00:00Z"
        self.EventType = "BaseEventType"
        self.SourceName = "SRC"
        self.Message = "msg"
        self.Severity = 1
        self.ConditionName = "cond"
        self.EventId = "evt-1"
        if condition_id is not None:
            self.ConditionId = condition_id
        if retain is not None:
            self.Retain = retain
        if active_state is not None:
            self.ActiveState = active_state
        if acked_state is not None:
            self.AckedState = acked_state

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "DummyEvent"


def test_tui_alarm_handler_ensure_header_and_event_flow(tmp_path: Path) -> None:
    csv_path = tmp_path / "alarms.csv"
    app = _DummyApp(messages=[])
    handler = TuiAlarmHandler(str(csv_path), app)

    # Header should have been created.
    header = csv_path.read_text(encoding="utf-8").splitlines()[0]
    assert "timestamp_utc" in header

    event = _DummyEvent(
        condition_id=_DummyNodeId("ns=1;i=42"),
        retain=True,
        active_state=_DummyState(True),
        acked_state=_DummyState(False),
    )

    handler.event_notification(event)

    # CSV now has header + one row.
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    # Active alarms map updated.
    active = handler.get_active_alarms()
    assert "ns=1;i=42" in active

    # App received an AlarmRow message.
    assert len(app.messages) == 1
    assert isinstance(app.messages[0], AlarmRow)
    assert app.messages[0].row["condition_id"] == "ns=1;i=42"

