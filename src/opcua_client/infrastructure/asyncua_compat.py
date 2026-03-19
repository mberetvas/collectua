from __future__ import annotations


def patch_create_session_server_uri(client, replacement_server_uri: str) -> None:
    """
    Work around asyncua generating ``urn:localhost`` / ``urn:127.0.0.1`` as
    CreateSessionParameters.ServerUri for local endpoints.

    Some servers reject that value with BadServerUriInvalid. In that narrow
    case, rewrite it to a caller-provided server URI before the request is sent.
    """
    uaclient = getattr(client, "uaclient", None)
    if uaclient is None or getattr(uaclient, "_opcua_client_server_uri_patched", False):
        return
    if not hasattr(uaclient, "create_session"):
        return

    original_create_session = uaclient.create_session

    async def _patched_create_session(parameters):
        if getattr(parameters, "ServerUri", "") in {"urn:localhost", "urn:127.0.0.1"}:
            parameters.ServerUri = replacement_server_uri
        return await original_create_session(parameters)

    uaclient.create_session = _patched_create_session
    uaclient._opcua_client_server_uri_patched = True
