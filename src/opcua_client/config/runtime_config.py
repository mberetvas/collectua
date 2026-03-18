from __future__ import annotations

import json

from dataclasses import asdict, dataclass, field

from .env_defaults import get_bool, get_float, get_int, get_int_list, get_str


@dataclass
class FileLoggingConfig:
    """Per-connection file logging configuration."""

    enabled: bool = field(default_factory=lambda: get_bool("OPCUA_LOG_FILE_ENABLED", False))
    path: str = field(default_factory=lambda: get_str("OPCUA_LOG_FILE_PATH", "logs/debug"))
    name_pattern: str = field(
        default_factory=lambda: get_str("OPCUA_LOG_FILE_NAME_PATTERN", "debug-{timestamp}-pid{pid}.log")
    )


@dataclass
class LoggingConfig:
    """Per-connection logging configuration."""

    level: str = field(default_factory=lambda: get_str("OPCUA_LOG_LEVEL", "INFO"))  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    file: FileLoggingConfig = field(default_factory=FileLoggingConfig)


@dataclass
class ConnectionConfig:
    url: str = field(default_factory=lambda: get_str("OPCUA_URL", ""))
    timeout: float = field(default_factory=lambda: get_float("OPCUA_TIMEOUT", 30.0))
    session_timeout: int = field(default_factory=lambda: get_int("OPCUA_SESSION_TIMEOUT", 60000))
    request_timeout: int = field(default_factory=lambda: get_int("OPCUA_REQUEST_TIMEOUT", 20000))
    username: str = field(default_factory=lambda: get_str("OPCUA_USERNAME", ""))
    password: str = field(default_factory=lambda: get_str("OPCUA_PASSWORD", ""))
    auth_policy: str = field(default_factory=lambda: get_str("OPCUA_AUTH_POLICY", "None"))
    security_mode: str = field(default_factory=lambda: get_str("OPCUA_SECURITY_MODE", "None_"))
    cert_file: str = field(default_factory=lambda: get_str("OPCUA_CERT_FILE", ""))
    key_file: str = field(default_factory=lambda: get_str("OPCUA_KEY_FILE", ""))
    server_cert: str = field(default_factory=lambda: get_str("OPCUA_SERVER_CERT", ""))
    trust_cert: bool = field(default_factory=lambda: get_bool("OPCUA_TRUST_CERT", False))
    logging_config: LoggingConfig | None = None


@dataclass
class BrowseConfig:
    max_depth: int = field(default_factory=lambda: get_int("OPCUA_MAX_DEPTH", 3))
    target_namespaces: list[int] = field(default_factory=lambda: get_int_list("OPCUA_TARGET_NAMESPACES", []))


@dataclass
class CollectConfig:
    csv_file: str = field(default_factory=lambda: get_str("OPCUA_CSV_FILE", "alarms.csv"))
    publish_interval_ms: int = field(default_factory=lambda: get_int("OPCUA_PUBLISH_INTERVAL_MS", 500))
    reconnect_delay_sec: int = field(default_factory=lambda: get_int("OPCUA_RECONNECT_DELAY_SEC", 5))


@dataclass
class RuntimeConfig:
    command: str = ""
    log_level: str = field(default_factory=lambda: get_str("OPCUA_LOG_LEVEL", "INFO"))
    connection: ConnectionConfig = field(default_factory=ConnectionConfig)
    browse: BrowseConfig = field(default_factory=BrowseConfig)
    collect: CollectConfig = field(default_factory=CollectConfig)
    mode: str = field(default_factory=lambda: get_str("OPCUA_MODE", "prod"))
    debug_log_dir: str = field(default_factory=lambda: get_str("OPCUA_DEBUG_LOG_DIR", "logs/debug"))

    @classmethod
    def from_namespace(cls, args) -> "RuntimeConfig":
        # Extract and build logging config from args if present
        logging_config = None
        logging_dict = getattr(args, "logging", None)
        if logging_dict and isinstance(logging_dict, dict):
            file_dict = logging_dict.get("file", {})
            if isinstance(file_dict, dict):
                file_config = FileLoggingConfig(
                    enabled=file_dict.get("enabled", get_bool("OPCUA_LOG_FILE_ENABLED", False)),
                    path=file_dict.get("path", get_str("OPCUA_LOG_FILE_PATH", "logs/debug")),
                    name_pattern=file_dict.get(
                        "name_pattern",
                        get_str("OPCUA_LOG_FILE_NAME_PATTERN", "debug-{timestamp}-pid{pid}.log"),
                    ),
                )
            else:
                file_config = FileLoggingConfig()

            logging_config = LoggingConfig(
                level=logging_dict.get("level", get_str("OPCUA_LOG_LEVEL", "INFO")),
                file=file_config,
            )

        return cls(
            command=getattr(args, "command", ""),
            log_level=getattr(args, "log_level", get_str("OPCUA_LOG_LEVEL", "INFO")),
            mode=getattr(args, "mode", get_str("OPCUA_MODE", "prod")),
            debug_log_dir=getattr(args, "debug_log_dir", get_str("OPCUA_DEBUG_LOG_DIR", "logs/debug")),
            connection=ConnectionConfig(
                url=getattr(args, "url", get_str("OPCUA_URL", "")),
                timeout=float(getattr(args, "timeout", get_float("OPCUA_TIMEOUT", 30.0))),
                session_timeout=int(getattr(args, "session_timeout", get_int("OPCUA_SESSION_TIMEOUT", 60000))),
                request_timeout=int(getattr(args, "request_timeout", get_int("OPCUA_REQUEST_TIMEOUT", 20000))),
                username=getattr(args, "username", get_str("OPCUA_USERNAME", "")),
                password=getattr(args, "password", get_str("OPCUA_PASSWORD", "")),
                auth_policy=getattr(args, "auth_policy", get_str("OPCUA_AUTH_POLICY", "None")),
                security_mode=getattr(args, "security_mode", get_str("OPCUA_SECURITY_MODE", "None_")),
                cert_file=getattr(args, "cert_file", get_str("OPCUA_CERT_FILE", "")),
                key_file=getattr(args, "key_file", get_str("OPCUA_KEY_FILE", "")),
                server_cert=getattr(args, "server_cert", get_str("OPCUA_SERVER_CERT", "")),
                trust_cert=bool(getattr(args, "trust_cert", get_bool("OPCUA_TRUST_CERT", False))),
                logging_config=logging_config,
            ),
            browse=BrowseConfig(
                max_depth=int(getattr(args, "max_depth", get_int("OPCUA_MAX_DEPTH", 3))),
                target_namespaces=[int(ns) for ns in getattr(args, "target_namespace", get_int_list("OPCUA_TARGET_NAMESPACES", []))],
            ),
            collect=CollectConfig(
                csv_file=getattr(args, "csv_file", get_str("OPCUA_CSV_FILE", "alarms.csv")),
                publish_interval_ms=int(getattr(args, "publish_interval_ms", get_int("OPCUA_PUBLISH_INTERVAL_MS", 500))),
                reconnect_delay_sec=int(getattr(args, "reconnect_delay_sec", get_int("OPCUA_RECONNECT_DELAY_SEC", 5))),
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

        if self.browse.max_depth < 0:
            errors.append("max_depth must be >= 0")

        for ns in self.browse.target_namespaces:
            if ns < 0:
                errors.append("target_namespace values must be >= 0")
                break

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

