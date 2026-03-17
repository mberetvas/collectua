import asyncio
import logging
import socket

from dataclasses import dataclass
from asyncua import Client, Node, ua

from opcua_client.env_defaults import get_float, get_formatted_str, get_int, get_str


@dataclass
class ClientConfigSecure:
    url: str = get_str("OPCUA_EXAMPLE_URL", "opc.tcp://10.205.139.4:4840")
    username: str = get_str("OPCUA_EXAMPLE_USERNAME", "OPCGB")
    password: str = get_str("OPCUA_EXAMPLE_PASSWORD", "OPCgb123!")
    auth_policy: str = get_str(
        "OPCUA_EXAMPLE_AUTH_POLICY", "Basic256"
    )  # Options: "None" (for None_ mode), "Basic128Rsa15", "Basic256", "Basic256Sha256"
    security_mode: str = get_str("OPCUA_EXAMPLE_SECURITY_MODE", "Sign")  # Options: "None_", "Sign", "SignAndEncrypt"
    cert_file: str = get_str("OPCUA_EXAMPLE_CERT_FILE", "")
    key_file: str = get_str("OPCUA_EXAMPLE_KEY_FILE", "")
    log_level: int = logging.INFO
    timeout: float = get_float("OPCUA_EXAMPLE_TIMEOUT", 30.0)  # Socket communication timeout in seconds
    session_timeout: int = get_int(
        "OPCUA_EXAMPLE_SESSION_TIMEOUT", 60000
    )  # Session timeout in milliseconds (negotiated with server)
    request_timeout: int = get_int(
        "OPCUA_EXAMPLE_REQUEST_TIMEOUT", 20000
    )  # Individual request timeout in milliseconds for session activation and operations


@dataclass
class ClientConfigInsecure:
    url: str = get_str("OPCUA_EXAMPLE_URL", "opc.tcp://10.205.139.4:4840")
    username: str = ""
    password: str = ""
    auth_policy: str = get_str(
        "OPCUA_AUTH_POLICY", "None"
    )  # Options: "None" (for None_ mode), "Basic128Rsa15", "Basic256", "Basic256Sha256"
    security_mode: str = get_str("OPCUA_SECURITY_MODE", "None_")  # Options: "None_", "Sign", "SignAndEncrypt"
    cert_file: str = ""
    key_file: str = ""
    log_level: int = logging.INFO
    timeout: float = get_float("OPCUA_TIMEOUT", 30.0)  # Socket communication timeout in seconds
    session_timeout: int = get_int(
        "OPCUA_SESSION_TIMEOUT", 60000
    )  # Session timeout in milliseconds (negotiated with server)
    request_timeout: int = get_int(
        "OPCUA_REQUEST_TIMEOUT", 20000
    )  # Individual request timeout in milliseconds for session activation and operations


_logger = logging.getLogger("asyncua")


async def browse_nodes(node: Node):
    """
    Build a nested node tree dict by recursion (filtered by OPC UA objects and variables).
    """
    node_class = await node.read_node_class()
    children = []
    for child in await node.get_children(
        nodeclassmask=ua.NodeClass.Object | ua.NodeClass.Variable | ua.NodeClass.Method
    ):
        children.append(await browse_nodes(child))
    if children:
        children.sort(key=lambda c: str(c.get("name", "")).lower())
    if node_class != ua.NodeClass.Variable:
        var_type = None
    else:
        try:
            var_type = (await node.read_data_type_as_variant_type()).value
        except ua.UaError:
            _logger.warning("Node Variable Type could not be determined for %r", node)
            var_type = None
    return {
        "id": node.nodeid.to_string(),
        "name": (await node.read_display_name()).Text,
        "cls": node_class.value,
        "children": children,
        "type": var_type,
    }


async def task(config: ClientConfigInsecure):
    """
    Connect to OPC UA server and browse the address space.

    Timeout Configuration Notes:

    - Server-side limits: The server enforces its own maximum session timeout. The client
      requests a timeout value during session creation, but the server may return a lower
      value. Check log output to see the negotiated timeout (e.g., "got 30000ms instead").
      Increasing client-side timeout won't override server limits.

    - Keep-alive strategy: For long-lived connections where the client may be idle,
      implement keep-alive by calling client.get_keepalive_count() to determine when
      to send notifications. This prevents the server from closing idle sessions.
      Recommended keep-alive interval: 75% of negotiated session timeout.

    - Async timeout handling: The 'timeout' parameter (in seconds) applies to socket-level
      communication and request handling. Separate timeouts exist for:
      * Connection establishment (socket timeout)
      * Individual request/response cycles (request timeout)
      * Session lifetime (session timeout in milliseconds)
      Longer timeouts allow more time for handshakes and server-side session validation.
    """
    try:
        client = Client(url=config.url, timeout=config.timeout)
        # Matches the URI defined in generate_certificates.py
        client.application_uri = get_formatted_str(
            "OPCUA_CLIENT_APP_URI_TEMPLATE",
            "urn:{hostname}:foobar:myclient",
            hostname=socket.gethostname(),
        )
        # Configure session and request timeouts before connection
        client.session_timeout = config.session_timeout
        client.uaclient.request_timeout = config.request_timeout
        _logger.info(
            "Requesting session timeout of %dms, request timeout %dms", config.session_timeout, config.request_timeout
        )
        # Set authentication policy if needed (commented out for basic username/password auth)
        if config.security_mode != "None_":
            # Only set security for non-None modes
            await client.set_security_string(
                f"{config.auth_policy},{config.security_mode},{config.cert_file},{config.key_file}"
            )
        await client.connect()
        # Log actual negotiated session timeout from server
        _logger.info("Connected. Negotiated session timeout: %dms", client.session_timeout)
        # Client has a few methods to get proxy to UA nodes that should always be in address space such as Root or Objects
        root = client.nodes.root
        _logger.info("Objects node is: %r", root)

        # Node objects have methods to read and write node attributes as well as browse or populate address space
        _logger.info("Children of root are: %r", await root.get_children())

        tree = await browse_nodes(client.nodes.objects)
        _logger.info("Node tree: %r", tree)
    except Exception:
        _logger.exception("error")
    finally:
        await client.disconnect()


def main():
    config = ClientConfigInsecure()
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    asyncio.run(task(config))


if __name__ == "__main__":
    main()
