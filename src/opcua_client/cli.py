import argparse
import asyncio
import logging
import socket

from asyncua import Client

from . import browse, collector
from .runtime_config import RuntimeConfig


def _configure_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


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
            if not conn.cert_file or not conn.key_file:
                raise ValueError("--cert-file and --key-file are required when security mode is not None_")
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
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity",
    )

    subparsers = parser.add_subparsers(dest="command")

    browse_parser = subparsers.add_parser("browse", help="Browse OPC UA node tree")
    browse_parser.add_argument("--url", default=browse.ENDPOINT, help="OPC UA endpoint URL")
    browse_parser.add_argument("--max-depth", type=int, default=browse.MAX_DEPTH, help="Browse depth")
    browse_parser.add_argument("--timeout", type=float, default=browse.TIMEOUT, help="Socket timeout (seconds)")

    collect_parser = subparsers.add_parser("collect", help="Subscribe to alarms/events and write CSV")
    collect_parser.add_argument("--url", default=collector.ENDPOINT, help="OPC UA endpoint URL")
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
        default=collector.TIMEOUT,
        help="Socket timeout (seconds)",
    )

    connect_parser = subparsers.add_parser("connect", help="Connection smoke test (supports secure/insecure)")
    connect_parser.add_argument("--url", default="opc.tcp://10.205.139.4:4840", help="OPC UA endpoint URL")
    connect_parser.add_argument("--timeout", type=float, default=30.0, help="Socket timeout (seconds)")
    connect_parser.add_argument("--session-timeout", type=int, default=60000, help="Session timeout (milliseconds)")
    connect_parser.add_argument("--request-timeout", type=int, default=20000, help="Request timeout (milliseconds)")
    connect_parser.add_argument("--username", default="", help="Username for user/password auth")
    connect_parser.add_argument("--password", default="", help="Password for user/password auth")
    connect_parser.add_argument(
        "--auth-policy",
        default="None",
        choices=["None", "Basic128Rsa15", "Basic256", "Basic256Sha256"],
        help="Security policy",
    )
    connect_parser.add_argument(
        "--security-mode",
        default="None_",
        choices=["None_", "Sign", "SignAndEncrypt"],
        help="Security mode",
    )
    connect_parser.add_argument("--cert-file", default="", help="Client certificate path")
    connect_parser.add_argument("--key-file", default="", help="Client private key path")

    config_parser = subparsers.add_parser("config", help="Show or validate normalized runtime configuration")
    config_parser.add_argument("--url", default="opc.tcp://10.205.139.4:4840", help="OPC UA endpoint URL")
    config_parser.add_argument("--timeout", type=float, default=30.0, help="Socket timeout (seconds)")
    config_parser.add_argument("--session-timeout", type=int, default=60000, help="Session timeout (milliseconds)")
    config_parser.add_argument("--request-timeout", type=int, default=20000, help="Request timeout (milliseconds)")
    config_parser.add_argument("--username", default="", help="Username for user/password auth")
    config_parser.add_argument("--password", default="", help="Password for user/password auth")
    config_parser.add_argument(
        "--auth-policy",
        default="None",
        choices=["None", "Basic128Rsa15", "Basic256", "Basic256Sha256"],
        help="Security policy",
    )
    config_parser.add_argument(
        "--security-mode",
        default="None_",
        choices=["None_", "Sign", "SignAndEncrypt"],
        help="Security mode",
    )
    config_parser.add_argument("--cert-file", default="", help="Client certificate path")
    config_parser.add_argument("--key-file", default="", help="Client private key path")
    config_parser.add_argument("--max-depth", type=int, default=browse.MAX_DEPTH, help="Browse depth")
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

    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    config = RuntimeConfig.from_namespace(args)
    errors = config.validate()

    if args.command != "config" and errors:
        for error in errors:
            print(f"[config error] {error}")
        return 2

    _configure_logging(args.log_level)

    if args.command == "browse":
        asyncio.run(
            browse.run(
                endpoint=config.connection.url,
                max_depth=config.browse.max_depth,
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
