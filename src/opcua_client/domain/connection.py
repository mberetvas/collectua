from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .exceptions import ConnectionValidationError, InvalidOPCUAUrl, InvalidSecurityMode


class SecurityMode(str, Enum):
    NONE = "None_"
    SIGN = "Sign"
    SIGN_AND_ENCRYPT = "SignAndEncrypt"

    @classmethod
    def from_value(cls, value: str | None) -> "SecurityMode":
        if value is None:
            return cls.NONE
        for mode in cls:
            if mode.value.lower() == value.lower():
                return mode
        raise InvalidSecurityMode(f"Unsupported security mode: {value}")


class AuthPolicy(str, Enum):
    """
    OPC UA *security policy* (not user authentication method).

    Note: user authentication is determined separately by credentials (anonymous vs username/password),
    while this field selects the security policy used for the secure channel.
    
    Enum values use OPC UA URI format (with underscores, e.g. Aes128_Sha256_RsaOaep).
    Use to_asyncua_format() when passing to asyncua's set_security_string() which expects
    format without underscores (e.g. Aes128Sha256RsaOaep).
    """

    NONE = "None"
    BASIC128RSA15 = "Basic128Rsa15"
    BASIC256 = "Basic256"
    BASIC256SHA256 = "Basic256Sha256"
    AES128_SHA256_RSAOAEP = "Aes128_Sha256_RsaOaep"
    AES256_SHA256_RSAPSS = "Aes256_Sha256_RsaPss"

    @classmethod
    def from_value(cls, value: str | None) -> "AuthPolicy":
        if value is None:
            return cls.NONE
        normalized = value.strip()
        if not normalized:
            return cls.NONE
        if normalized.lower() in {"none"}:
            return cls.NONE
        # Handle both OPC UA format (with underscores) and asyncua format (without)
        for policy in cls:
            if policy.value.lower() == normalized.lower():
                return policy
            # Try matching asyncua format (without underscores)
            asyncua_fmt = policy.to_asyncua_format()
            if asyncua_fmt.lower() == normalized.lower():
                return policy
        # Unknown policy -> treat as None to keep backward compatibility.
        return cls.NONE

    def to_asyncua_format(self) -> str:
        """
        Convert to asyncua's expected format (no underscores).
        
        OPC UA uses underscores in security policy names (e.g., Aes128_Sha256_RsaOaep),
        but asyncua SecurityPolicy classes don't (e.g., SecurityPolicyAes128Sha256RsaOaep).
        """
        return self.value.replace("_", "")

    @classmethod
    def from_asyncua_format(cls, value: str) -> "AuthPolicy":
        """Convert from asyncua format (no underscores) to enum."""
        if not value:
            return cls.NONE
        normalized = value.strip().lower()
        for policy in cls:
            asyncua_fmt = policy.to_asyncua_format().lower()
            if asyncua_fmt == normalized:
                return policy
        return cls.NONE


@dataclass(frozen=True)
class Credentials:
    username: str = ""
    password: str = ""

    def is_username_auth(self) -> bool:
        return bool(self.username)

    def is_certificate_auth(self) -> bool:
        return not self.username and not self.password


@dataclass(frozen=True)
class OPCUAConnection:
    url: str
    timeout: float
    session_timeout: int
    request_timeout: int
    security_mode: SecurityMode
    auth_policy: AuthPolicy
    credentials: Credentials
    cert_file: str = ""
    key_file: str = ""
    server_cert: str = ""
    trust_cert: bool = False

    def __post_init__(self) -> None:
        if not self.url.startswith("opc.tcp://"):
            raise InvalidOPCUAUrl("url must start with opc.tcp://")
        if self.timeout <= 0:
            raise ConnectionValidationError("timeout must be greater than 0")
        if self.session_timeout <= 0:
            raise ConnectionValidationError("session_timeout must be greater than 0")
        if self.request_timeout <= 0:
            raise ConnectionValidationError("request_timeout must be greater than 0")

    @classmethod
    def from_values(
        cls,
        *,
        url: str,
        timeout: float = 30.0,
        session_timeout: int = 60000,
        request_timeout: int = 20000,
        security_mode: str | None = None,
        auth_policy: str | None = None,
        username: str = "",
        password: str = "",
        cert_file: str = "",
        key_file: str = "",
        server_cert: str = "",
        trust_cert: bool = False,
    ) -> "OPCUAConnection":
        return cls(
            url=url,
            timeout=float(timeout),
            session_timeout=int(session_timeout),
            request_timeout=int(request_timeout),
            security_mode=SecurityMode.from_value(security_mode),
            auth_policy=AuthPolicy.from_value(auth_policy),
            credentials=Credentials(username=username, password=password),
            cert_file=cert_file,
            key_file=key_file,
            server_cert=server_cert,
            trust_cert=trust_cert,
        )

    def is_secure(self) -> bool:
        return self.security_mode != SecurityMode.NONE

    def requires_client_cert(self) -> bool:
        return self.is_secure() and bool(self.cert_file and self.key_file)

    def is_trusted(self) -> bool:
        return self.trust_cert or not self.is_secure()
