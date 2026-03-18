from __future__ import annotations

from argparse import Namespace

from opcua_client.domain.connection import OPCUAConnection
from opcua_client.infrastructure.config_loader import load_connection_from_cli_args, load_connection_from_profile


class ConnectionService:
    """Use-case: resolve a domain connection from inputs."""

    def from_cli_args(self, args: Namespace) -> OPCUAConnection:
        return load_connection_from_cli_args(args)

    def from_profile(self, profile_name: str) -> OPCUAConnection:
        return load_connection_from_profile(profile_name)

