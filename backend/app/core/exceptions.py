class DomainError(Exception):
    """Base class for all domain-specific errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class DuplicateEmailError(DomainError):
    """Raised when attempting to register with an already registered email."""

    def __init__(self, message: str = "A user with this email address already exists.") -> None:
        super().__init__(message)


class InvalidCredentialsError(DomainError):
    """Raised when authentication fails due to bad credentials or inactive account."""

    def __init__(self, message: str = "Incorrect email or password.") -> None:
        super().__init__(message)


class InactiveUserError(DomainError):
    """Raised when an inactive user attempts to log in."""

    def __init__(self, message: str = "User account is disabled.") -> None:
        super().__init__(message)


class InvalidTokenError(DomainError):
    """Raised when a provided token is corrupt, improperly signed, or incorrect type."""

    def __init__(self, message: str = "Invalid or malformed token.") -> None:
        super().__init__(message)


class TokenRevokedError(DomainError):
    """Raised when an expired or revoked token is used."""

    def __init__(self, message: str = "Token has been revoked or expired.") -> None:
        super().__init__(message)


class SecurityCompromisedError(DomainError):
    """Raised upon detecting refresh token replay attacks (reuse of revoked tokens)."""

    def __init__(
        self,
        message: str = "Potential token theft detected. All active sessions have been revoked.",
    ) -> None:
        super().__init__(message)