from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass

from opcua_client.infrastructure.asyncua_adapter import (
    create_connection_from_runtime_config,
    event_to_alarm,
    node_to_domain_node,
)
from opcua_client.config.runtime_config import RuntimeConfig


@dataclass
class _DummyEvent:
    ConditionId: str = "ns=2;s=alarm-1"
    ConditionName: str = "Overheat"
    SourceName: str = "Motor1"
    Message: str = "too hot"
    Severity: int = 900
    Time: str = "2024-01-01T00:00:00Z"
    EventType: str = "ConditionType"
    EventId: str = "evt-1"
    Retain: bool = True
    ActiveState: bool = True
    AckedState: bool = False


class _DummyNodeId:
    def __init__(self, value: str) -> None:
        self._value = value
        self.NamespaceIndex = 2

    def to_string(self) -> str:
        return self._value


class _DummyNode:
    def __init__(self) -> None:
        self.nodeid = _DummyNodeId("ns=2;s=Tag1")
        self.name = "Tag1"
        self.node_class = "Variable"


def test_event_to_alarm_maps_fields() -> None:
    alarm = event_to_alarm(_DummyEvent())
    assert str(alarm.alarm_id) == "ns=2;s=alarm-1"
    assert alarm.condition_name == "Overheat"
    assert alarm.is_retained() is True


def test_event_to_alarm_formats_program_alarm_placeholders() -> None:
    @dataclass
    class _ProgramAlarmEvent:
        ConditionId: str = "ns=2;s=alarm-2"
        ConditionName: str = "ProgramAlarm"
        SourceName: str = "PLC1"
        Message: str = "Error @1%d@ on @2%s@"
        Arguments: list[object] = None  # type: ignore[assignment]
        Severity: int = 500
        Time: str = "2024-01-01T00:00:00Z"
        EventType: str = "Program_Alarm"
        EventId: bytes = b"\x01\x02"
        Retain: bool = True
        ActiveState: bool = True
        AckedState: bool = False

        def __post_init__(self) -> None:
            self.Arguments = [404, "PumpA"]

    alarm = event_to_alarm(_ProgramAlarmEvent())

    assert alarm.message == "Error 404 on PumpA"
    assert alarm.event_id == "0102"
    assert alarm.event_id_bytes == b"\x01\x02"


def test_event_to_alarm_marks_unresolved_program_alarm_placeholders() -> None:
    @dataclass
    class _ProgramAlarmEvent:
        ConditionId: str = "ns=2;s=alarm-3"
        ConditionName: str = "ProgramAlarm"
        SourceName: str = "PLC1"
        Message: str = "Error @1%d@ on @2%s@"
        Arguments: list[object] = None  # type: ignore[assignment]
        Severity: int = 500
        Time: str = "2024-01-01T00:00:00Z"
        EventType: str = "Program_Alarm"
        EventId: str = "evt-2"
        Retain: bool = True
        ActiveState: bool = True
        AckedState: bool = False

        def __post_init__(self) -> None:
            self.Arguments = [404]

    alarm = event_to_alarm(_ProgramAlarmEvent())

    assert alarm.message == "Error @1%d@ on @2%s@ [unresolved]"


def test_node_to_domain_node_maps_node() -> None:
    node = node_to_domain_node(_DummyNode())
    assert str(node.node_id) == "ns=2;s=Tag1"
    assert node.namespace_index == 2
    assert node.is_variable() is True


def test_create_connection_from_runtime_config() -> None:
    runtime = RuntimeConfig.from_namespace(
        Namespace(
            command="config",
            url="opc.tcp://server:4840",
            timeout=10.0,
            session_timeout=60000,
            request_timeout=20000,
            username="",
            password="",
            auth_policy="None",
            security_mode="None_",
            cert_file="",
            key_file="",
            server_cert="",
            trust_cert=False,
            locales=["en-US"],
            overloads_node_id="ns=3;s=Overloads",
            max_depth=3,
            target_namespace=[],
            csv_file="alarms.csv",
            publish_interval_ms=500,
            reconnect_delay_sec=5,
            mode="prod",
            log_level="INFO",
            debug_log_dir=".collectua/logs",
            logging=None,
        )
    )
    connection = create_connection_from_runtime_config(runtime)
    assert connection.url == "opc.tcp://server:4840"
