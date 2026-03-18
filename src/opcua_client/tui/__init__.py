import argparse
import sys

from opcua_client.config.env_defaults import get_int_list, get_str
from opcua_client.config.profile_loader import list_profiles, load_profile
from opcua_client.config.runtime_config import RuntimeConfig
from opcua_client.ops import browse, collector

from .app import OpcuaTuiApp


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opcua-tui",
        description="OPC UA command center TUI (htop/btop-inspired)",
    )
    parser.add_argument(
        "--mode",
        choices=["prod", "debug"],
        default=get_str("OPCUA_MODE", "prod"),
        help="Runtime mode",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=get_str("OPCUA_LOG_LEVEL", "INFO"),
        help="Console logging level",
    )
    parser.add_argument(
        "--debug-log-dir",
        default=get_str("OPCUA_DEBUG_LOG_DIR", "logs/debug"),
        help="Directory for debug log files",
    )

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
    parser.add_argument("--server-cert", default=argparse.SUPPRESS, help="Server certificate path metadata")
    parser.add_argument(
        "--trust-cert",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Mark the server certificate as trusted for this connection (skips interactive trust prompt)",
    )
    parser.add_argument(
        "--locales",
        nargs="*",
        default=argparse.SUPPRESS,
        help="Preferred OPC UA session LocaleIds (space-separated, e.g. en-US de-DE)",
    )
    parser.add_argument(
        "--overloads-node-id",
        default=argparse.SUPPRESS,
        help="Optional NodeId for the Siemens Overloads state monitor",
    )

    parser.add_argument("--max-depth", type=int, default=browse.MAX_DEPTH, help="Browse depth")
    parser.add_argument(
        "--target-namespace",
        type=int,
        nargs="*",
        default=get_int_list("OPCUA_TARGET_NAMESPACES", []),
        help="Optional namespace index filter (space-separated). Empty means all namespaces.",
    )
    parser.add_argument(
        "--csv-file",
        default=collector.CSV_FILE,
        help="Output CSV file path",
    )
    parser.add_argument(
        "--publish-interval-ms",
        type=int,
        default=collector.PUBLISH_INTERVAL_MS,
        help="Subscription publish interval",
    )
    parser.add_argument(
        "--reconnect-delay-sec",
        type=int,
        default=collector.RECONNECT_DELAY_SEC,
        help="Reconnect delay in seconds",
    )

    return parser


def _choose_profile_name(profiles: list[str]) -> str | None:
    print("Available connection profiles:")
    for idx, name in enumerate(profiles, start=1):
        display = name
        try:
            payload = load_profile(name)
            friendly = str(payload.get("friendly_name", "")).strip()
            url = str(payload.get("url", "")).strip()
            if friendly:
                if url:
                    display = f"{friendly} ({name}, {url})"
                else:
                    display = f"{friendly} ({name})"
            elif url:
                display = f"{url} ({name})"
        except Exception:
            # Fall back to the raw profile name if loading fails for any reason.
            display = name
        print(f"  {idx}. {display}")
    print("Select a profile number (or 'q' to cancel): ", end="", flush=True)

    while True:
        value = input().strip()
        if value.lower() in {"q", "quit", "exit"}:
            return None
        if value.isdigit():
            selected = int(value)
            if 1 <= selected <= len(profiles):
                return profiles[selected - 1]
        print("Invalid selection. Enter a number from the list, or 'q' to cancel: ", end="", flush=True)


def main(argv=None) -> int:
    parser = _build_parser()
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(raw_argv)
    args.command = "tui"

    if not raw_argv and not getattr(args, "connection_profile", None):
        profiles = list_profiles()
        if not profiles:
            print(
                "No connection profiles available. Create one in ./connections/ or "
                "~/.config/opcua-client/connections/, or launch opcua-tui with connection args."
            )
            return 2
        selected_profile = _choose_profile_name(profiles)
        if not selected_profile:
            print("No profile selected. Exiting.")
            return 2
        args.connection_profile = selected_profile

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
    if errors:
        for error in errors:
            print(f"[config error] {error}")
        return 2

    app = OpcuaTuiApp(config)
    app.run()
    return 0
