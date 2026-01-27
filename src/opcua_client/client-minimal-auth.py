import asyncio
import logging

from dataclasses import dataclass
from asyncua import Client, Node, ua

@dataclass
class ClientConfig:
    url: str = "opc.tcp://10.205.139.4:4840"
    username: str = "OPCGB"
    password: str = "OPCgb123!"
    auth_policy: str = "Basic256"  # Options: "Basic128Rsa15", "Basic256", "Basic256Sha256"
    security_mode: str = "SignAndEncrypt"
    cert_file: str = "certs-example/certs/myclient-selfsigned.der"
    key_file: str = "certs-example/private/myclient.pem"
    log_level: int = logging.DEBUG


_logger = logging.getLogger("asyncua")


async def browse_nodes(node: Node):
    """
    Build a nested node tree dict by recursion (filtered by OPC UA objects and variables).
    """
    node_class = await node.read_node_class()
    children = []
    for child in await node.get_children():
        if await child.read_node_class() in [ua.NodeClass.Object, ua.NodeClass.Variable]:
            children.append(await browse_nodes(child))
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


async def task(config: ClientConfig):
    try:
        client = Client(url=config.url)
        client.set_user(config.username)
        client.set_password(config.password)
        # Set authentication policy if needed (commented out for basic username/password auth)
        client.set_security_string(f"{config.auth_policy},{config.security_mode},{config.cert_file},{config.key_file}")
        await client.connect()
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
    config = ClientConfig()
    logging.basicConfig(level=config.log_level)
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.run_until_complete(task(config))
    loop.close()


if __name__ == "__main__":
    main()