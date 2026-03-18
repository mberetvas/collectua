class DomainException(Exception):
    """Base exception for domain-level invariants and validation errors."""


class InvalidAlarmSeverity(DomainException):
    """Raised when an alarm severity cannot be mapped to a supported value."""


class AlarmValidationError(DomainException):
    """Raised when alarm entity construction violates an invariant."""


class InvalidOPCUAUrl(DomainException):
    """Raised when an OPC UA endpoint URL is malformed."""


class InvalidSecurityMode(DomainException):
    """Raised when an unsupported security mode is provided."""


class ConnectionValidationError(DomainException):
    """Raised when connection entity construction violates an invariant."""


class InvalidNodeId(DomainException):
    """Raised when a node identifier is empty or malformed."""


class NodeValidationError(DomainException):
    """Raised when node entity construction violates an invariant."""


class SubscriptionFailed(DomainException):
    """Raised when a domain-level subscription operation fails."""
