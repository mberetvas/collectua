from __future__ import annotations

import re

from datetime import datetime, timezone
from typing import Any, Sequence

from asyncua import ua

from opcua_client.domain.alarm import Alarm
from opcua_client.domain.connection import OPCUAConnection
from opcua_client.domain.node import Node, NodeClass, NodeId
from opcua_client.config.runtime_config import RuntimeConfig


def event_to_alarm(event: Any) -> Alarm:
    event_id_bytes = _event_id_bytes_from_event(event)
    return Alarm.from_values(
        alarm_id=_condition_id_from_event(event),
        condition_name=str(getattr(event, "ConditionName", "unknown-condition")),
        source_name=str(getattr(event, "SourceName", "unknown-source")),
        message=_message_from_event(event),
        severity=getattr(event, "Severity", None),
        timestamp_utc=getattr(event, "Time", datetime.now(timezone.utc)),
        retain=_bool_or_none(getattr(event, "Retain", None)),
        active_state=_bool_or_none(getattr(event, "ActiveState", None)),
        acked_state=_bool_or_none(getattr(event, "AckedState", None)),
        event_type=str(getattr(event, "EventType", "")),
        event_id=_event_id_text(event_id_bytes),
        event_id_bytes=event_id_bytes,
        raw=str(event),
    )


def node_to_domain_node(node: Any) -> Node:
    nodeid_raw = getattr(node, "nodeid", None)
    browse_name_raw = getattr(node, "name", "")
    browse_name = str(browse_name_raw)
    display_name = str(getattr(node, "name", browse_name))

    if nodeid_raw is not None and hasattr(nodeid_raw, "to_string"):
        node_id = NodeId.from_value(nodeid_raw.to_string())
        namespace_index = int(getattr(nodeid_raw, "NamespaceIndex", 0))
    else:
        node_id = NodeId.from_value(str(nodeid_raw or browse_name or "unknown"))
        namespace_index = 0

    node_class_raw = getattr(node, "node_class", None)
    return Node(
        node_id=node_id,
        display_name=display_name,
        browse_name=browse_name if browse_name else display_name,
        node_class=NodeClass.from_value(node_class_raw),
        namespace_index=namespace_index,
    )


def create_connection_from_runtime_config(runtime_config: RuntimeConfig) -> OPCUAConnection:
    connection = runtime_config.connection
    return OPCUAConnection.from_values(
        url=connection.url,
        timeout=connection.timeout,
        session_timeout=connection.session_timeout,
        request_timeout=connection.request_timeout,
        security_mode=connection.security_mode,
        auth_policy=connection.auth_policy,
        username=connection.username,
        password=connection.password,
        cert_file=connection.cert_file,
        key_file=connection.key_file,
        server_cert=connection.server_cert,
        trust_cert=connection.trust_cert,
    )


def _condition_id_from_event(event: Any) -> str:
    value = getattr(event, "ConditionId", None)
    if value is None:
        fallback = getattr(event, "EventId", None)
        if fallback is not None:
            return str(fallback)
        return "unknown-condition-id"
    if isinstance(value, ua.NodeId):
        return value.to_string()
    to_string = getattr(value, "to_string", None)
    if callable(to_string):
        return str(to_string())
    return str(value)


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    inner = getattr(value, "Id", value)
    try:
        return bool(inner)
    except Exception:
        return None


_PROGRAM_ALARM_PLACEHOLDER_RE = re.compile(r"@(\d+)%([A-Za-z])@")


def format_program_alarm_message(message: str, args: Sequence[Any]) -> str:
    placeholders = list(_PROGRAM_ALARM_PLACEHOLDER_RE.finditer(message))
    if not placeholders:
        return message

    formatted = message
    for match in reversed(placeholders):
        index = int(match.group(1)) - 1
        specifier = match.group(2).lower()
        if specifier not in {"s", "d", "i", "f", "x"}:
            continue
        if index < 0 or index >= len(args):
            return f"{message} [unresolved]"
        formatted = f"{formatted[:match.start()]}{_stringify_program_alarm_arg(args[index], specifier)}{formatted[match.end():]}"
    return formatted


def _message_from_event(event: Any) -> str:
    raw_message = _localized_text_to_str(getattr(event, "Message", ""))
    if not raw_message:
        return raw_message

    if not _PROGRAM_ALARM_PLACEHOLDER_RE.search(raw_message):
        return raw_message

    return format_program_alarm_message(raw_message, _event_arguments(event))


def _event_arguments(event: Any) -> list[Any]:
    for attr in ("Arguments", "ClientSpecifiedValues", "ClientSpecifiedValue", "InputArguments"):
        value = getattr(event, attr, None)
        if value is None:
            continue
        if isinstance(value, (str, bytes, bytearray)):
            return [value]
        try:
            return list(value)
        except TypeError:
            return [value]
    return []


def _localized_text_to_str(value: Any) -> str:
    text = getattr(value, "Text", None)
    if text is not None:
        return str(text)
    return str(value)


def _stringify_program_alarm_arg(value: Any, specifier: str) -> str:
    if specifier in {"d", "i"}:
        return str(int(value))
    if specifier == "f":
        return str(float(value))
    if specifier == "x":
        return format(int(value), "x")
    return str(value)


def _event_id_bytes_from_event(event: Any) -> bytes:
    value = getattr(event, "EventId", None)
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    return str(value).encode("utf-8")


def _event_id_text(event_id: bytes) -> str:
    if not event_id:
        return ""
    try:
        decoded = event_id.decode("utf-8")
    except UnicodeDecodeError:
        return event_id.hex()
    if decoded.isprintable():
        return decoded
    return event_id.hex()
