import argparse

from opcua_client.runtime_config import RuntimeConfig

from .app import OpcuaTuiApp


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opcua-tui",
        description="OPC UA command center TUI (htop/btop-inspired)",
    )
    parser.add_argument("--mode", choices=["prod", "debug"], default="prod", help="Runtime mode")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Console logging level",
    )
    parser.add_argument("--debug-log-dir", default="logs/debug", help="Directory for debug log files")

    parser.add_argument("--url", required=True, help="OPC UA endpoint URL")
    parser.add_argument("--timeout", type=float, default=30.0, help="Socket timeout (seconds)")
    parser.add_argument("--session-timeout", type=int, default=60000, help="Session timeout (milliseconds)")
    parser.add_argument("--request-timeout", type=int, default=20000, help="Request timeout (milliseconds)")
    parser.add_argument("--username", default="", help="Username for user/password auth")
    parser.add_argument("--password", default="", help="Password for user/password auth")
    parser.add_argument(
        "--auth-policy",
        default="None",
        choices=["None", "Basic128Rsa15", "Basic256", "Basic256Sha256"],
        help="Security policy",
    )
    parser.add_argument(
        "--security-mode",
        default="None_",
        choices=["None_", "Sign", "SignAndEncrypt"],
        help="Security mode",
    )
    parser.add_argument("--cert-file", default="", help="Client certificate path")
    parser.add_argument("--key-file", default="", help="Client private key path")

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

    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    args.command = "tui"

    config = RuntimeConfig.from_namespace(args)
    errors = config.validate()
    if errors:
        for error in errors:
            print(f"[config error] {error}")
        return 2

    app = OpcuaTuiApp(config)
    app.run()
    return 0
