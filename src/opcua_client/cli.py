import argparse
import asyncio
import logging
import os
import socket
from datetime import datetime
from pathlib import Path

from asyncua import Client

from . import browse, collector
from .cert_paths import ensure_client_certificates
from .profile_autosetup import ensure_profile_for_url_interactive
from .profile_loader import list_profiles, load_profile
from .runtime_config import RuntimeConfig


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
    from .runtime_config import ConnectionConfig

    # Get root logger and clear any existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Determine console level: connection config takes precedence
    console_level_str = log_level.upper()
    if connection_config and connection_config.logging_config:
        console_level_str = connection_config.logging_config.level.upper()
    console_level = getattr(logging, console_level_str, logging.INFO)

    # Determine file logging settings
    file_enabled = False
    file_level = logging.DEBUG
    file_dir = Path(debug_log_dir)
    file_name_pattern = "debug-{timestamp}-pid{pid}.log"

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


async def _connect_smoke(config: RuntimeConfig):
    """Connection smoke test command (supports insecure and secure modes)."""
    conn = config.connection
    logger = logging.getLogger("connect")
    client = Client(url=conn.url, timeout=conn.timeout)
    client.application_uri = f"urn:{socket.gethostname()}:foobar:myclient"
    client.session_timeout = conn.session_timeout
    client.uaclient.request_timeout = conn.request_timeout

    if conn.username:
        client.set_user(conn.username)
    if conn.password:
        client.set_password(conn.password)

    try:
        if conn.security_mode != "None_":
            # If no explicit cert/key paths are provided via CLI/profile,
            # auto-generate or resolve client certificates.
            if not conn.cert_file or not conn.key_file:
                cert_file, key_file = ensure_client_certificates()
                conn.cert_file = cert_file
                conn.key_file = key_file
            await client.set_security_string(
                f"{conn.auth_policy},{conn.security_mode},{conn.cert_file},{conn.key_file}"
            )

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
        prog="opcua-client",
        description="OPC UA command center CLI",
    )
    parser.add_argument(
        "--mode",
        choices=["prod", "debug"],
        default="prod",
        help="Runtime mode: 'prod' (default, INFO level console-only) or 'debug' (DEBUG level with per-run log file)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Console logging level (overrides mode defaults)",
    )
    parser.add_argument(
        "--debug-log-dir",
        default="logs/debug",
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
        choices=["None", "Basic128Rsa15", "Basic256", "Basic256Sha256"],
        help="Security policy",
    )
    parser.add_argument(
        "--security-mode",
        default=argparse.SUPPRESS,
        choices=["None_", "Sign", "SignAndEncrypt"],
        help="Security mode",
    )
    parser.add_argument("--cert-file", default=argparse.SUPPRESS, help="Client certificate path")
    parser.add_argument("--key-file", default=argparse.SUPPRESS, help="Client private key path")
    parser.add_argument("--max-depth", type=int, default=3, help="Browse depth")
    parser.add_argument(
        "--target-namespace",
        type=int,
        nargs="*",
        default=[],
        help="Optional namespace index filter (space-separated). Empty means all namespaces.",
    )
    parser.add_argument("--csv-file", default="alarms.csv", help="Output CSV file path")
    parser.add_argument("--publish-interval-ms", type=int, default=500, help="Subscription publish interval")
    parser.add_argument("--reconnect-delay-sec", type=int, default=5, help="Reconnect delay in seconds")

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
        default=[],
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
    connect_parser.add_argument(
        "--session-timeout", type=int, default=argparse.SUPPRESS, help="Session timeout (milliseconds)"
    )
    connect_parser.add_argument(
        "--request-timeout", type=int, default=argparse.SUPPRESS, help="Request timeout (milliseconds)"
    )
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
    connect_parser.add_argument("--cert-file", default=argparse.SUPPRESS, help="Client certificate path")
    connect_parser.add_argument("--key-file", default=argparse.SUPPRESS, help="Client private key path")

    config_parser = subparsers.add_parser("config", help="Show or validate normalized runtime configuration")
    _add_connection_profile_arg(config_parser)
    config_parser.add_argument("--url", default=argparse.SUPPRESS, help="OPC UA endpoint URL")
    config_parser.add_argument("--timeout", type=float, default=argparse.SUPPRESS, help="Socket timeout (seconds)")
    config_parser.add_argument(
        "--session-timeout", type=int, default=argparse.SUPPRESS, help="Session timeout (milliseconds)"
    )
    config_parser.add_argument(
        "--request-timeout", type=int, default=argparse.SUPPRESS, help="Request timeout (milliseconds)"
    )
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
    config_parser.add_argument("--cert-file", default=argparse.SUPPRESS, help="Client certificate path")
    config_parser.add_argument("--key-file", default=argparse.SUPPRESS, help="Client private key path")
    config_parser.add_argument("--max-depth", type=int, default=browse.MAX_DEPTH, help="Browse depth")
    config_parser.add_argument(
        "--target-namespace",
        type=int,
        nargs="*",
        default=[],
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

    list_profiles_parser = subparsers.add_parser("list-profiles", help="List available connection profiles")

    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Handle --tui flag
    if args.tui:
        if args.command:
            parser.error("--tui cannot be used with subcommands")
        # Import TUI app here to avoid circular imports and keep TUI optional
        from .tui.app import OpcuaTuiApp

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
                    "~/.config/opcua-client/connections/, or launch opcua-client with connection args."
                )
                return 2
            # Use TUI profile chooser function
            from .tui import _choose_profile_name

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
