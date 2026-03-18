from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from asyncua import ua

from opcua_client.domain.alarm import Alarm
from opcua_client.domain.connection import OPCUAConnection
from opcua_client.domain.node import Node, NodeClass, NodeId
from opcua_client.config.runtime_config import RuntimeConfig


def event_to_alarm(event: Any) -> Alarm:
    return Alarm.from_values(
        alarm_id=_condition_id_from_event(event),
        condition_name=str(getattr(event, "ConditionName", "unknown-condition")),
        source_name=str(getattr(event, "SourceName", "unknown-source")),
        message=str(getattr(event, "Message", "")),
        severity=getattr(event, "Severity", None),
        timestamp_utc=getattr(event, "Time", datetime.now(timezone.utc)),
        retain=_bool_or_none(getattr(event, "Retain", None)),
        active_state=_bool_or_none(getattr(event, "ActiveState", None)),
        acked_state=_bool_or_none(getattr(event, "AckedState", None)),
        event_type=str(getattr(event, "EventType", "")),
        event_id=str(getattr(event, "EventId", "")),
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
