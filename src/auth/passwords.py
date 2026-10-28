"""Argon2id helpers shared by bootstrap and a future login service."""

from argon2 import PasswordHasher
from argon2.exceptions import HashingError, InvalidHashError, VerificationError
from argon2.low_level import Type


# RFC 9106 low-memory profile; the library generates a fresh random salt.
_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4,
                         hash_len=32, salt_len=16, type=Type.ID)
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_BYTES = 1024


def _password_valid(password):
    if not isinstance(password, str) or not password or password.isspace():
        return False
    try:
        return len(password) >= MIN_PASSWORD_LENGTH and len(password.encode("utf-8")) <= MAX_PASSWORD_BYTES
    except UnicodeError:
        return False


def hash_password(password):
    """Hash exactly the provided string; never trim or log a password."""
    if not _password_valid(password):
        raise ValueError("Password minimal 12 karakter, maksimal 1024 byte UTF-8, dan tidak seluruhnya spasi.")
    try:
        return _HASHER.hash(password)
    except HashingError:
        raise ValueError("Hashing password gagal.") from None


def verify_password(encoded_hash, password):
    """Return False for mismatch/missing/invalid Argon2id hash; no DB mutation.

    encoded_hash must come from the trusted database, never a client upload.
    This checks a password only; a future login must also check account status
    and roles, manage sessions, and apply its authentication controls.
    """
    if (not isinstance(encoded_hash, str) or not encoded_hash.startswith("$argon2id$")
            or len(encoded_hash) > 255 or not _password_valid(password)):
        return False
    try:
        return _HASHER.verify(encoded_hash, password)
    except (VerificationError, InvalidHashError):
        return False
