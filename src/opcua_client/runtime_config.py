from __future__ import annotations

import json

from dataclasses import asdict, dataclass


@dataclass
class ConnectionConfig:
    url: str
    timeout: float
    session_timeout: int = 60000
    request_timeout: int = 20000
    username: str = ""
    password: str = ""
    auth_policy: str = "None"
    security_mode: str = "None_"
    cert_file: str = ""
    key_file: str = ""


@dataclass
class BrowseConfig:
    max_depth: int = 3


@dataclass
class CollectConfig:
    csv_file: str = "alarms.csv"
    publish_interval_ms: int = 500
    reconnect_delay_sec: int = 5


@dataclass
class RuntimeConfig:
    command: str
    log_level: str
    connection: ConnectionConfig
    browse: BrowseConfig
    collect: CollectConfig

    @classmethod
    def from_namespace(cls, args) -> "RuntimeConfig":
        return cls(
            command=getattr(args, "command", ""),
            log_level=getattr(args, "log_level", "INFO"),
            connection=ConnectionConfig(
                url=getattr(args, "url", "opc.tcp://10.205.139.4:4840"),
                timeout=float(getattr(args, "timeout", 30.0)),
                session_timeout=int(getattr(args, "session_timeout", 60000)),
                request_timeout=int(getattr(args, "request_timeout", 20000)),
                username=getattr(args, "username", ""),
                password=getattr(args, "password", ""),
                auth_policy=getattr(args, "auth_policy", "None"),
                security_mode=getattr(args, "security_mode", "None_"),
                cert_file=getattr(args, "cert_file", ""),
                key_file=getattr(args, "key_file", ""),
            ),
            browse=BrowseConfig(max_depth=int(getattr(args, "max_depth", 3))),
            collect=CollectConfig(
                csv_file=getattr(args, "csv_file", "alarms.csv"),
                publish_interval_ms=int(getattr(args, "publish_interval_ms", 500)),
                reconnect_delay_sec=int(getattr(args, "reconnect_delay_sec", 5)),
            ),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []

        if not self.connection.url.startswith("opc.tcp://"):
            errors.append("url must start with opc.tcp://")

        if self.connection.timeout <= 0:
            errors.append("timeout must be greater than 0")

        if self.connection.session_timeout <= 0:
            errors.append("session_timeout must be greater than 0")

        if self.connection.request_timeout <= 0:
            errors.append("request_timeout must be greater than 0")

        if self.connection.security_mode != "None_":
            if not self.connection.cert_file:
                errors.append("cert_file is required when security_mode is not None_")
            if not self.connection.key_file:
                errors.append("key_file is required when security_mode is not None_")

        if self.browse.max_depth < 0:
            errors.append("max_depth must be >= 0")

        if self.collect.publish_interval_ms <= 0:
            errors.append("publish_interval_ms must be greater than 0")

        if self.collect.reconnect_delay_sec < 0:
            errors.append("reconnect_delay_sec must be >= 0")

        return errors

    def as_dict(self, mask_sensitive: bool = True) -> dict:
        data = asdict(self)
        if mask_sensitive and data["connection"]["password"]:
            data["connection"]["password"] = "********"
        return data

    def as_json(self, mask_sensitive: bool = True) -> str:
        return json.dumps(self.as_dict(mask_sensitive=mask_sensitive), indent=2)
