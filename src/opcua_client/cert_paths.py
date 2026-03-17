from __future__ import annotations

import logging
import socket
from dataclasses import dataclass
from pathlib import Path

from asyncua.crypto.cert_gen import (
    dump_private_key_as_pem,
    generate_private_key,
    generate_self_signed_app_certificate,
)
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, load_pem_private_key
from cryptography.x509.oid import ExtendedKeyUsageOID

from .env_defaults import get_formatted_str, get_path, get_str

_logger = logging.getLogger("certs")


@dataclass(frozen=True)
class ClientCertPaths:
    base_dir: Path
    cert_dir: Path
    private_dir: Path
    cert_file: Path
    key_file: Path


def _config_base_dir() -> Path:
    """
    Return the base directory for config-scoped certificates, under
    ~/.config/opcua-client/certs.
    """
    return get_path("OPCUA_FALLBACK_CERT_BASE_DIR", "~/.config/opcua-client/certs")


def _ensure_base_dirs(base_dir: Path) -> ClientCertPaths:
    """
    Ensure certificate and private key directories exist under the given base.
    """
    cert_dir = base_dir / "certs"
    private_dir = base_dir / "private"

    cert_dir.mkdir(parents=True, exist_ok=True)
    private_dir.mkdir(parents=True, exist_ok=True)

    cert_file = cert_dir / get_str("OPCUA_CLIENT_CERT_FILENAME", "myclient-selfsigned.der")
    key_file = private_dir / get_str("OPCUA_CLIENT_KEY_FILENAME", "myclient.pem")

    return ClientCertPaths(
        base_dir=base_dir,
        cert_dir=cert_dir,
        private_dir=private_dir,
        cert_file=cert_file,
        key_file=key_file,
    )


def get_default_client_cert_paths() -> ClientCertPaths:
    """
    Resolve default client certificate paths using this strategy:

    1. Prefer ./certs/ relative to the current working directory. Create it
       (and subdirectories) if it does not exist.
    2. If that fails for any reason (e.g., permissions), fall back to
       ~/.config/opcua-client/certs.
    """
    cwd_base = get_path("OPCUA_CERT_BASE_DIR", "certs", relative_to_cwd=True)

    try:
        return _ensure_base_dirs(cwd_base)
    except Exception:
        _logger.exception("Failed to use ./certs directory, falling back to config directory")

    config_base = _config_base_dir()
    return _ensure_base_dirs(config_base)


def _generate_self_signed_client_certificate(paths: ClientCertPaths) -> None:
    """
    Generate a new self-signed client certificate and private key for OPC UA
    client usage.
    """
    hostname = socket.gethostname()

    names: dict[str, str] = {
        "countryName": get_str("OPCUA_CERT_COUNTRY", "BE"),
        "stateOrProvinceName": get_str("OPCUA_CERT_STATE", "Gent"),
        "localityName": get_str("OPCUA_CERT_LOCALITY", "GB"),
        "organizationName": get_str("OPCUA_CERT_ORG", "VCG"),
    }

    subject_alt_names: list[x509.GeneralName] = [
        x509.UniformResourceIdentifier(
            get_formatted_str("OPCUA_CLIENT_APP_URI_TEMPLATE", "urn:{hostname}:foobar:myclient", hostname=hostname)
        ),
        x509.DNSName(hostname),
    ]

    extended_uses = [ExtendedKeyUsageOID.CLIENT_AUTH]

    key = generate_private_key()
    cert: x509.Certificate = generate_self_signed_app_certificate(
        key,
        f"myclient@{hostname}",
        names,
        subject_alt_names,
        extended=extended_uses,
    )

    # Persist private key (PEM) and certificate (DER)
    paths.private_dir.mkdir(parents=True, exist_ok=True)
    paths.cert_dir.mkdir(parents=True, exist_ok=True)

    paths.key_file.write_bytes(dump_private_key_as_pem(key))
    paths.cert_file.write_bytes(cert.public_bytes(encoding=Encoding.DER))

    _logger.info("Generated new client certificate at %s and key at %s", paths.cert_file, paths.key_file)


def ensure_client_certificates() -> tuple[str, str]:
    """
    Ensure that client certificate and key files exist and are valid.

    - If both files exist and can be parsed, they are reused.
    - If either is missing or invalid, new self-signed artifacts are created.

    Returns:
        Tuple of (cert_path_str, key_path_str) suitable for asyncua Client.set_security_string.
    """
    paths = get_default_client_cert_paths()

    needs_generation = False

    if not paths.cert_file.exists() or not paths.key_file.exists():
        needs_generation = True
    else:
        try:
            # Basic validation: ensure both certificate and key can be loaded
            # using cryptography in a synchronous context.
            cert_bytes = paths.cert_file.read_bytes()
            key_bytes = paths.key_file.read_bytes()
            _ = x509.load_der_x509_certificate(cert_bytes)
            _ = load_pem_private_key(key_bytes, password=None)
        except Exception:
            _logger.exception("Existing client certificate/key invalid; regenerating")
            needs_generation = True

    if needs_generation:
        try:
            _generate_self_signed_client_certificate(paths)
        except Exception as exc:
            raise RuntimeError(
                "Failed to generate OPC UA client certificates automatically. "
                "Install 'asyncua[crypto]' / 'cryptography' and ensure write access to the certs directory, "
                "or provide --cert-file/--key-file explicitly."
            ) from exc

    return str(paths.cert_file), str(paths.key_file)
