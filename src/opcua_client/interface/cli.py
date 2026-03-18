import argparse
import asyncio
import logging
import os
import socket
import sys
from datetime import datetime
from pathlib import Path

import yaml
from asyncua import Client, ua

from ..config.env_defaults import get_bool, get_formatted_str, get_int_list, get_str
from ..config.profile_autosetup import ensure_profile_for_url_interactive
from ..config.profile_loader import list_profiles, load_profile, resolve_profile_path
from ..config.runtime_config import RuntimeConfig
from ..infrastructure.config_loader import load_connection_from_cli_args
from ..ops import browse, collector
from ..security.cert_paths import ensure_client_certificates


def _configure_logging(
    mode: str,
    log_level: str,
    debug_log_dir: str = "logs/debug",
    connection_config: "ConnectionConfig | None" = None,
) -> str | None:
    """
    Configure logging with optional file handler for debug mode or per-connection settings.

    Args:
        mode: 'prod' or 'debug'
        log_level: User-specified log level (DEBUG, INFO, WARNING, ERROR)
        debug_log_dir: Directory for debug log files (only used in debug mode)
        connection_config: Optional connection config with logging configuration

    Returns:
        Path to debug log file if created, else None
    """
    from ..config.runtime_config import ConnectionConfig

    # Get root logger and clear any existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Determine console level: connection config takes precedence
    console_level_str = log_level.upper()
    if connection_config and connection_config.logging_config:
        console_level_str = connection_config.logging_config.level.upper()
    console_level = getattr(logging, console_level_str, logging.INFO)

    # Determine file logging settings
    file_enabled = get_bool("OPCUA_LOG_FILE_ENABLED", False)
    file_level = logging.DEBUG
    file_dir = Path(debug_log_dir)
    file_name_pattern = get_str("OPCUA_LOG_FILE_NAME_PATTERN", "debug-{timestamp}-pid{pid}.log")

    if connection_config and connection_config.logging_config:
        file_config = connection_config.logging_config.file
        file_enabled = file_config.enabled
        file_dir = Path(file_config.path)
        file_name_pattern = file_config.name_pattern
    elif mode == "debug":
        file_enabled = True

    # Console handler (always present)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if enabled)
    debug_log_file = None
    if file_enabled:
        # Ensure log directory exists
        file_dir.mkdir(parents=True, exist_ok=True)

        # Create unique filename using pattern
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        pid = os.getpid()
        debug_log_file = file_dir / file_name_pattern.format(timestamp=timestamp, pid=pid)

        file_handler = logging.FileHandler(debug_log_file)
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Set root logger to lowest level to allow handlers to filter
    if file_enabled:
        root_logger.setLevel(logging.DEBUG)
    else:
        root_logger.setLevel(console_level)

    return str(debug_log_file) if debug_log_file else None


def _short_policy_from_uri(policy_uri: str) -> str:
    """
    Extract short policy name from a SecurityPolicy URI, e.g. ...#Basic256Sha256.
    """
    if not policy_uri:
        return "None"
    if "#" in policy_uri:
        return policy_uri.rsplit("#", 1)[-1] or "None"
    return policy_uri


# #region agent log
def _agent_log(*, runId: str, hypothesisId: str, location: str, message: str, data: dict) -> None:
    """
    Debug-mode NDJSON logger for this Cursor session.
    Writes to: debug-3adc8d.log
    """
    import json
    import time

    payload = {
        "sessionId": "3adc8d",
        "runId": runId,
        "hypothesisId": hypothesisId,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open("debug-3adc8d.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


# #endregion agent log


async def _collect_server_certificate(config: RuntimeConfig) -> bytes:
    """
    Connect to the OPC UA endpoint in discovery mode and collect the server
    certificate for the configured security policy/mode.
    """
    conn = config.connection
    client = Client(url=conn.url, timeout=conn.timeout)
    try:
        endpoints = await client.connect_and_get_server_endpoints()
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    if not endpoints:
        raise RuntimeError(f"No endpoints discovered for OPC UA server at {conn.url}")

    desired_policy = conn.auth_policy or "None"
    desired_mode = conn.security_mode or "None_"

    # #region agent log
    _agent_log(
        runId="pre-fix",
        hypothesisId="A",
        location="src/opcua_client/interface/cli.py:_collect_server_certificate:desired",
        message="Computed desired security selector from connection config",
        data={
            "url": conn.url,
            "conn_auth_policy_type": type(conn.auth_policy).__name__,
            "conn_auth_policy_value": str(conn.auth_policy),
            "conn_security_mode_type": type(conn.security_mode).__name__,
            "conn_security_mode_value": str(conn.security_mode),
            "desired_policy": str(desired_policy),
            "desired_mode": str(desired_mode),
        },
    )
    # #endregion agent log

    matched_cert: bytes | None = None
    ep_summaries: list[dict] = []
    for ep in endpoints:
        policy_uri = getattr(ep, "SecurityPolicyUri", "") or ""
        policy_short = _short_policy_from_uri(policy_uri)

        mode = getattr(ep, "SecurityMode", ua.MessageSecurityMode.None_)
        mode_name = mode.name
        security_mode = "None_" if mode_name == "None" else mode_name

        raw_cert = getattr(ep, "ServerCertificate", b"") or b""
        cert_len = len(raw_cert) if not isinstance(raw_cert, memoryview) else raw_cert.nbytes
        ep_summaries.append(
            {
                "policy_short": policy_short,
                "security_mode": security_mode,
                "policy_uri": policy_uri,
                "cert_len": cert_len,
            }
        )

        if policy_short != desired_policy or security_mode != desired_mode:
            continue

        # asyncua may expose this as bytes, bytearray or memoryview.
        if isinstance(raw_cert, memoryview):
            matched_cert = bytes(raw_cert)
        else:
            matched_cert = bytes(raw_cert)
        break

    if not matched_cert:
        # #region agent log
        _agent_log(
            runId="pre-fix",
            hypothesisId="A",
            location="src/opcua_client/interface/cli.py:_collect_server_certificate:no-match",
            message="No endpoint matched desired policy/mode (or cert was empty)",
            data={
                "desired_policy": str(desired_policy),
                "desired_mode": str(desired_mode),
                "endpoint_count": len(endpoints),
                "endpoints": ep_summaries[:12],
            },
        )
        # #endregion agent log
        raise RuntimeError(
            f"No server certificate available for endpoint with policy={desired_policy}, " f"mode={desired_mode} at {conn.url}"
        )

    return matched_cert


def _format_cert_fingerprint(cert_bytes: bytes) -> str:
    import hashlib

    digest = hashlib.sha256(cert_bytes).hexdigest()
    # Group into colon-separated pairs for readability.
    return ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))


def _persist_trust_to_profile(
    profile_name: str,
    server_cert_path: Path,
) -> None:
    """
    Persist trust metadata to the given profile YAML.
    """
    from ..config import profile_loader

    payload = profile_loader.load_profile(profile_name)
    payload["server_cert"] = str(server_cert_path)
    payload["trust_cert"] = True

    profile_path = resolve_profile_path(profile_name)
    # Serialize before opening the target file to avoid truncating it on serialization errors.
    serialized = yaml.safe_dump(payload, sort_keys=False)
    with profile_path.open("w", encoding="utf-8") as handle:
        handle.write(serialized)


async def _ensure_server_trust(config: RuntimeConfig, profile_name: str | None) -> None:
    """
    Ensure that the server certificate for this connection is trusted.

    - Automatically collects the server certificate from the endpoint.
    - If trust_cert is False, prompts the user to trust the certificate.
    - On acceptance, persists trust and server_cert path when a profile is available.
    """
    conn = config.connection

    # No certificate in insecure mode.
    if conn.security_mode == "None_":
        return

    # Already trusted for this connection, nothing to do.
    if conn.trust_cert:
        return

    # Collect server certificate bytes from endpoints.
    cert_bytes = await _collect_server_certificate(config)
    fingerprint = _format_cert_fingerprint(cert_bytes)

    # If we have a profile, store the certificate next to the profile file.
    cert_path: Path | None = None
    if profile_name:
        profile_path = resolve_profile_path(profile_name)
        cert_path = profile_path.with_suffix(".der")
    else:
        print("[trust warning] No connection profile associated with this connection; server trust will not be persisted.")

    print("")
    print("The OPC UA server certificate for this connection is not yet trusted.")
    if cert_path is not None:
        print(f"Planned certificate file: {cert_path}")
    print(f"SHA-256 fingerprint: {fingerprint}")
    print("")

    if not sys.stdin.isatty():
        raise RuntimeError(
            "Server certificate is untrusted and interactive confirmation is required, "
            "but no TTY is available. Run in an interactive terminal or mark the "
            "certificate as trusted via profile/CLI."
        )

    answer = input("Do you want to trust this server certificate? [y/N]: ").strip().lower()
    if answer != "y":
        raise RuntimeError("Server certificate not trusted; aborting connection.")

    # User accepted trust for this run.
    conn.trust_cert = True

    if cert_path is not None:
        # Persist cert bytes and update profile YAML.
        cert_path.write_bytes(cert_bytes)
        _persist_trust_to_profile(profile_name, cert_path)
        print(f"Trusted server certificate written to {cert_path} and profile updated.")
    else:
        print("Trusted server certificate for this run only (no profile to persist).")


async def _connect_smoke(config: RuntimeConfig):
    """Connection smoke test command (supports insecure and secure modes)."""
    conn = config.connection
    logger = logging.getLogger("connect")
    client = Client(url=conn.url, timeout=conn.timeout)
    client.application_uri = get_formatted_str(
        "OPCUA_CLIENT_APP_URI_TEMPLATE",
        "urn:{hostname}:foobar:myclient",
        hostname=socket.gethostname(),
    )
    client.session_timeout = conn.session_timeout
    client.uaclient.request_timeout = conn.request_timeout

    if conn.username:
        client.set_user(conn.username)
    if conn.password:
        client.set_password(conn.password)

    try:
        if conn.security_mode != "None_":
            # Auto-generate or resolve client certificates (client-side).
            if conn.cert_file and conn.key_file:
                cert_file, key_file = conn.cert_file, conn.key_file
            else:
                cert_file, key_file = ensure_client_certificates()
            await client.set_security_string(f"{conn.auth_policy},{conn.security_mode},{cert_file},{key_file}")

        await client.connect()
        logger.info("Connected. Negotiated session timeout: %dms", client.session_timeout)
        root = client.nodes.root
        children = await root.get_children()
        logger.info("Root children count: %d", len(children))

    finally:
        await client.disconnect()
        logger.info("Disconnected")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="collectua",
        description="OPC UA command center CLI",
    )
    parser.add_argument(
        "--mode",
        choices=["prod", "debug"],
        default=get_str("OPCUA_MODE", "prod"),
        help="Runtime mode: 'prod' (default, INFO level console-only) or 'debug' (DEBUG level with per-run log file)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=get_str("OPCUA_LOG_LEVEL", "INFO"),
        help="Console logging level (overrides mode defaults)",
    )
    parser.add_argument(
        "--debug-log-dir",
        default=get_str("OPCUA_DEBUG_LOG_DIR", "logs/debug"),
        help="Directory for debug log files (only used in debug mode)",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Launch TUI dashboard (conflicts with subcommands)",
    )

    # Connection and TUI arguments available at top level for --tui flag
    parser.add_argument(
        "--connection-profile",
        default=None,
        help="Connection profile name from ./connections/ or ~/.config/opcua-client/connections/",
    )
    parser.add_argument("--url", default=argparse.SUPPRESS, help="OPC UA endpoint URL")
    parser.add_argument("--timeout", type=float, default=argparse.SUPPRESS, help="Socket timeout (seconds)")
    parser.add_argument("--session-timeout", type=int, default=argparse.SUPPRESS, help="Session timeout (milliseconds)")
    parser.add_argument("--request-timeout", type=int, default=argparse.SUPPRESS, help="Request timeout (milliseconds)")
    parser.add_argument("--username", default=argparse.SUPPRESS, help="Username for user/password auth")
    parser.add_argument("--password", default=argparse.SUPPRESS, help="Password for user/password auth")
    parser.add_argument(
        "--auth-policy",
        default=argparse.SUPPRESS,
        choices=[
            "None",
            "Basic128Rsa15",
            "Basic256",
            "Basic256Sha256",
            "Aes128_Sha256_RsaOaep",
            "Aes256_Sha256_RsaPss",
        ],
        help="Security policy",
    )
    parser.add_argument(
        "--security-mode",
        default=argparse.SUPPRESS,
        choices=["None_", "Sign", "SignAndEncrypt"],
        help="Security mode",
    )
    parser.add_argument("--server-cert", default=argparse.SUPPRESS, help="Server certificate path metadata")
    parser.add_argument(
        "--trust-cert",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Mark the server certificate as trusted for this connection (skips interactive trust prompt)",
    )
    parser.add_argument("--max-depth", type=int, default=browse.MAX_DEPTH, help="Browse depth")
    parser.add_argument(
        "--target-namespace",
        type=int,
        nargs="*",
        default=get_int_list("OPCUA_TARGET_NAMESPACES", []),
        help="Optional namespace index filter (space-separated). Empty means all namespaces.",
    )
    parser.add_argument("--csv-file", default=collector.CSV_FILE, help="Output CSV file path")
    parser.add_argument("--publish-interval-ms", type=int, default=collector.PUBLISH_INTERVAL_MS, help="Subscription publish interval")
    parser.add_argument("--reconnect-delay-sec", type=int, default=collector.RECONNECT_DELAY_SEC, help="Reconnect delay in seconds")

    subparsers = parser.add_subparsers(dest="command", required=False)

    def _add_connection_profile_arg(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument(
            "--connection-profile",
            default=None,
            help="Connection profile name from ./connections/ or ~/.config/opcua-client/connections/",
        )

    browse_parser = subparsers.add_parser("browse", help="Browse OPC UA node tree")
    _add_connection_profile_arg(browse_parser)
    browse_parser.add_argument("--url", default=argparse.SUPPRESS, help="OPC UA endpoint URL")
    browse_parser.add_argument("--max-depth", type=int, default=browse.MAX_DEPTH, help="Browse depth")
    browse_parser.add_argument(
        "--target-namespace",
        type=int,
        nargs="*",
        default=get_int_list("OPCUA_TARGET_NAMESPACES", []),
        help="Optional namespace index filter (space-separated). Empty means all namespaces.",
    )
    browse_parser.add_argument("--timeout", type=float, default=argparse.SUPPRESS, help="Socket timeout (seconds)")

    collect_parser = subparsers.add_parser("collect", help="Subscribe to alarms/events and write CSV")
    _add_connection_profile_arg(collect_parser)
    collect_parser.add_argument("--url", default=argparse.SUPPRESS, help="OPC UA endpoint URL")
    collect_parser.add_argument("--csv-file", default=collector.CSV_FILE, help="Output CSV file path")
    collect_parser.add_argument(
        "--publish-interval-ms",
        type=int,
        default=collector.PUBLISH_INTERVAL_MS,
        help="Subscription publish interval in milliseconds",
    )
    collect_parser.add_argument(
        "--reconnect-delay-sec",
        type=int,
        default=collector.RECONNECT_DELAY_SEC,
        help="Reconnect delay in seconds after errors",
    )
    collect_parser.add_argument(
        "--timeout",
        type=float,
        default=argparse.SUPPRESS,
        help="Socket timeout (seconds)",
    )

    connect_parser = subparsers.add_parser("connect", help="Connection smoke test (supports secure/insecure)")
    _add_connection_profile_arg(connect_parser)
    connect_parser.add_argument("--url", default=argparse.SUPPRESS, help="OPC UA endpoint URL")
    connect_parser.add_argument("--timeout", type=float, default=argparse.SUPPRESS, help="Socket timeout (seconds)")
    connect_parser.add_argument("--session-timeout", type=int, default=argparse.SUPPRESS, help="Session timeout (milliseconds)")
    connect_parser.add_argument("--request-timeout", type=int, default=argparse.SUPPRESS, help="Request timeout (milliseconds)")
    connect_parser.add_argument("--username", default=argparse.SUPPRESS, help="Username for user/password auth")
    connect_parser.add_argument("--password", default=argparse.SUPPRESS, help="Password for user/password auth")
    connect_parser.add_argument(
        "--auth-policy",
        default=argparse.SUPPRESS,
        choices=["None", "Basic128Rsa15", "Basic256", "Basic256Sha256"],
        help="Security policy",
    )
    connect_parser.add_argument(
        "--security-mode",
        default=argparse.SUPPRESS,
        choices=["None_", "Sign", "SignAndEncrypt"],
        help="Security mode",
    )
    connect_parser.add_argument("--server-cert", default=argparse.SUPPRESS, help="Server certificate path metadata")
    connect_parser.add_argument(
        "--trust-cert",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Mark the server certificate as trusted for this connection (skips interactive trust prompt)",
    )

    config_parser = subparsers.add_parser("config", help="Show or validate normalized runtime configuration")
    _add_connection_profile_arg(config_parser)
    config_parser.add_argument("--url", default=argparse.SUPPRESS, help="OPC UA endpoint URL")
    config_parser.add_argument("--timeout", type=float, default=argparse.SUPPRESS, help="Socket timeout (seconds)")
    config_parser.add_argument("--session-timeout", type=int, default=argparse.SUPPRESS, help="Session timeout (milliseconds)")
    config_parser.add_argument("--request-timeout", type=int, default=argparse.SUPPRESS, help="Request timeout (milliseconds)")
    config_parser.add_argument("--username", default=argparse.SUPPRESS, help="Username for user/password auth")
    config_parser.add_argument("--password", default=argparse.SUPPRESS, help="Password for user/password auth")
    config_parser.add_argument(
        "--auth-policy",
        default=argparse.SUPPRESS,
        choices=["None", "Basic128Rsa15", "Basic256", "Basic256Sha256"],
        help="Security policy",
    )
    config_parser.add_argument(
        "--security-mode",
        default=argparse.SUPPRESS,
        choices=["None_", "Sign", "SignAndEncrypt"],
        help="Security mode",
    )
    config_parser.add_argument("--server-cert", default=argparse.SUPPRESS, help="Server certificate path metadata")
    config_parser.add_argument(
        "--trust-cert",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Mark the server certificate as trusted for this connection (skips interactive trust prompt)",
    )
    config_parser.add_argument("--max-depth", type=int, default=browse.MAX_DEPTH, help="Browse depth")
    config_parser.add_argument(
        "--target-namespace",
        type=int,
        nargs="*",
        default=get_int_list("OPCUA_TARGET_NAMESPACES", []),
        help="Optional namespace index filter (space-separated). Empty means all namespaces.",
    )
    config_parser.add_argument("--csv-file", default=collector.CSV_FILE, help="Output CSV file path")
    config_parser.add_argument(
        "--publish-interval-ms",
        type=int,
        default=collector.PUBLISH_INTERVAL_MS,
        help="Subscription publish interval in milliseconds",
    )
    config_parser.add_argument(
        "--reconnect-delay-sec",
        type=int,
        default=collector.RECONNECT_DELAY_SEC,
        help="Reconnect delay in seconds after errors",
    )
    config_parser.add_argument(
        "--action",
        choices=["show", "validate"],
        default="show",
        help="Config command action",
    )
    config_parser.add_argument(
        "--show-secrets",
        action="store_true",
        help="Show sensitive values such as passwords in output",
    )

    subparsers.add_parser("list-profiles", help="List available connection profiles")

    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Handle --tui flag
    if args.tui:
        if args.command:
            parser.error("--tui cannot be used with subcommands")
        # Import TUI app here to avoid circular imports and keep TUI optional
        from ..tui.app import OpcuaTuiApp

        args.command = "tui"

        # URL-based auto-setup: when a URL is provided without an explicit profile,
        # discover security options and create or reuse a URL-specific profile.
        url_value = getattr(args, "url", None)
        if url_value and not getattr(args, "connection_profile", None):
            try:
                profile_name = ensure_profile_for_url_interactive(url_value)
            except RuntimeError as exc:
                print(f"[autosetup error] {exc}")
                return 2
            args.connection_profile = profile_name
            # Remove direct URL arg so profile values are authoritative.
            if hasattr(args, "url"):
                delattr(args, "url")

        # Interactive profile selection if no connection args provided
        if not any(getattr(args, attr, None) for attr in ["url", "connection_profile"]):
            profiles = list_profiles()
            if not profiles:
                print(
                    "No connection profiles available. Create one in ./connections/ or "
                    "~/.config/opcua-client/connections/, or launch collectua with connection args."
                )
                return 2
            # Use TUI profile chooser function
            from ..tui import _choose_profile_name

            selected_profile = _choose_profile_name(profiles)
            if not selected_profile:
                print("No profile selected. Exiting.")
                return 2
            args.connection_profile = selected_profile

        # Load profile if specified
        profile_name = getattr(args, "connection_profile", None)
        if profile_name:
            try:
                profile_values = load_profile(profile_name)
            except (FileNotFoundError, ValueError) as exc:
                print(f"[profile error] {exc}")
                return 2

            for key, value in profile_values.items():
                if not hasattr(args, key):
                    setattr(args, key, value)

        # Resolve + validate connection config via infrastructure loader
        try:
            resolved_connection = load_connection_from_cli_args(args)
        except Exception as exc:
            print(f"[config error] {exc}")
            return 2
        args.url = resolved_connection.url
        args.timeout = resolved_connection.timeout
        args.session_timeout = resolved_connection.session_timeout
        args.request_timeout = resolved_connection.request_timeout
        args.security_mode = resolved_connection.security_mode.value
        args.auth_policy = resolved_connection.auth_policy.value
        args.username = resolved_connection.credentials.username
        args.password = resolved_connection.credentials.password
        args.cert_file = resolved_connection.cert_file
        args.key_file = resolved_connection.key_file
        args.server_cert = resolved_connection.server_cert
        args.trust_cert = resolved_connection.trust_cert

        # Build and validate config
        config = RuntimeConfig.from_namespace(args)
        errors = config.validate()
        if errors:
            for error in errors:
                print(f"[config error] {error}")
            return 2

        # Configure logging with connection config
        debug_log_file = _configure_logging(config.mode, config.log_level, config.debug_log_dir, config.connection)
        if debug_log_file:
            logger = logging.getLogger("cli")
            logger.info(f"Debug log: {debug_log_file}")

        # Enforce server trust (interactive) before launching TUI.
        try:
            asyncio.run(_ensure_server_trust(config, profile_name))
        except RuntimeError as exc:
            print(f"[trust error] {exc}")
            return 2

        # Launch TUI
        app = OpcuaTuiApp(config)
        app.run()
        return 0

    # Handle standard commands
    if not args.command:
        parser.print_help()
        return 0

    if args.command == "list-profiles":
        profiles = list_profiles()
        if not profiles:
            print("No connection profiles found in ./connections/ or ~/.config/opcua-client/connections/")
            return 0
        print("Available connection profiles:")
        for name in profiles:
            print(f"  - {name}")
        return 0

    profile_name = getattr(args, "connection_profile", None)
    if profile_name:
        try:
            profile_values = load_profile(profile_name)
        except (FileNotFoundError, ValueError) as exc:
            print(f"[profile error] {exc}")
            return 2

        for key, value in profile_values.items():
            if not hasattr(args, key):
                setattr(args, key, value)

    # Resolve + validate connection config via infrastructure loader
    try:
        resolved_connection = load_connection_from_cli_args(args)
    except Exception as exc:
        print(f"[config error] {exc}")
        return 2
    args.url = resolved_connection.url
    args.timeout = resolved_connection.timeout
    args.session_timeout = resolved_connection.session_timeout
    args.request_timeout = resolved_connection.request_timeout
    args.security_mode = resolved_connection.security_mode.value
    args.auth_policy = resolved_connection.auth_policy.value
    args.username = resolved_connection.credentials.username
    args.password = resolved_connection.credentials.password
    args.cert_file = resolved_connection.cert_file
    args.key_file = resolved_connection.key_file
    args.server_cert = resolved_connection.server_cert
    args.trust_cert = resolved_connection.trust_cert

    config = RuntimeConfig.from_namespace(args)
    errors = config.validate()

    if args.command != "config" and errors:
        for error in errors:
            print(f"[config error] {error}")
        return 2

    # Configure logging with connection config
    debug_log_file = _configure_logging(config.mode, config.log_level, config.debug_log_dir, config.connection)
    if debug_log_file:
        logger = logging.getLogger("cli")
        logger.info(f"Debug log: {debug_log_file}")

    if args.command == "browse":
        asyncio.run(
            browse.run(
                endpoint=config.connection.url,
                max_depth=config.browse.max_depth,
                target_namespaces=config.browse.target_namespaces,
                timeout=config.connection.timeout,
            )
        )
        return 0

    if args.command == "collect":
        asyncio.run(
            collector.run(
                endpoint=config.connection.url,
                csv_file=config.collect.csv_file,
                publish_interval_ms=config.collect.publish_interval_ms,
                reconnect_delay_sec=config.collect.reconnect_delay_sec,
                timeout=config.connection.timeout,
            )
        )
        return 0

    if args.command == "connect":
        try:
            asyncio.run(_ensure_server_trust(config, profile_name))
        except RuntimeError as exc:
            print(f"[trust error] {exc}")
            return 2
        asyncio.run(_connect_smoke(config))
        return 0

    if args.command == "config":
        if args.action == "show":
            print(config.as_json(mask_sensitive=not args.show_secrets))
            return 0
        if args.action == "validate":
            if errors:
                print("Configuration is invalid:")
                for error in errors:
                    print(f"- {error}")
                return 2
            print("Configuration is valid.")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

