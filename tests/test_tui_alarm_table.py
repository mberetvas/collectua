from __future__ import annotations

from opcua_client.tui.widgets.alarm_table import AlarmTableWidget


def test_severity_style_for_alarm_severity_strings() -> None:
    assert AlarmTableWidget._severity_style("LOW") == "bold #8aff80"
    assert AlarmTableWidget._severity_style("MEDIUM") == "bold #ffbf4d"
    assert AlarmTableWidget._severity_style("HIGH") == "bold #ffbf4d"
    assert AlarmTableWidget._severity_style("CRITICAL") == "bold #ff5f5f"


def test_severity_style_for_numeric_strings() -> None:
    assert AlarmTableWidget._severity_style("200") == "bold #8aff80"
    assert AlarmTableWidget._severity_style("500") == "bold #ffbf4d"
    assert AlarmTableWidget._severity_style("900") == "bold #ff5f5f"


def test_severity_style_defaults_for_invalid_values() -> None:
    assert AlarmTableWidget._severity_style("unknown") == "bold #8aff80"
    assert AlarmTableWidget._severity_style(None) == "bold #8aff80"  # type: ignore[arg-type]
