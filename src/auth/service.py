"""Database-backed authentication and current role lookups. No result caching."""

from dataclasses import dataclass
import secrets

import pymysql

from src.auth.passwords import hash_password, verify_password
from src.auth.throttle import DEFAULT_LIMITER
from src.database.connection import get_connection


SUPPORTED_ROLES = frozenset({"admin","executive"})
LOGIN_FAILURE_MESSAGE = "Login tidak berhasil. Periksa kredensial atau coba lagi beberapa saat."
# Equal-cost verification for a missing account, without any usable fixed password.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


class LoginFailed(PermissionError):
    def __init__(self):
        super().__init__(LOGIN_FAILURE_MESSAGE)


class AuthenticationUnavailable(RuntimeError):
    def __init__(self):
        super().__init__("Layanan autentikasi sementara tidak tersedia.")


@dataclass(frozen=True)
class Principal:
    user_id: int
    username: str
    display_name: str
    roles: frozenset[str]


def _read_user(value, *, by_id, include_hash=False, connection_factory=None):
    connection = (connection_factory or get_connection)()
    try:
        with connection.cursor() as cursor:
            field = "u.user_id" if by_id else "u.username"
            secret_column = ",u.password_hash" if include_hash else ""
            cursor.execute("SELECT u.user_id,u.username,u.display_name,u.is_active,r.role_code" + secret_column +
                           " FROM app_users u LEFT JOIN app_user_roles r USING(user_id) WHERE " + field + "=%s",(value,))
            return list(cursor.fetchall())
    finally:
        connection.close()


def _principal(rows):
    if not rows or not rows[0]["is_active"]:
        return None
    roles = frozenset(row["role_code"] for row in rows if row["role_code"] in SUPPORTED_ROLES)
    if not roles:
        return None
    row = rows[0]
    return Principal(row["user_id"],row["username"],row["display_name"],roles)


def read_principal(user_id, *, connection_factory=None):
    if isinstance(user_id,bool) or not isinstance(user_id,int) or user_id <= 0:
        return None
    try:
        return _principal(_read_user(user_id,by_id=True,connection_factory=connection_factory))
    except (pymysql.MySQLError,OSError,ValueError):
        raise AuthenticationUnavailable() from None


def authenticate(username, password, *, connection_factory=None, limiter=DEFAULT_LIMITER, now=None):
    if not limiter.reserve(username,now=now):
        raise LoginFailed()
    if (not isinstance(username,str) or not username.strip() or len(username.strip()) > 100
            or not isinstance(password,str)):
        raise LoginFailed()
    username = username.strip()
    try:
        rows = _read_user(username,by_id=False,include_hash=True,connection_factory=connection_factory)
        encoded = rows[0].get("password_hash") if rows else None
        if not isinstance(encoded,str) or not encoded.startswith("$argon2id$"):
            encoded = _DUMMY_HASH
        valid_password = verify_password(encoded,password)
        initial = _principal(rows)
        if not valid_password or initial is None:
            raise LoginFailed()
        # Re-read status and roles after password verification in a fresh snapshot.
        principal = read_principal(initial.user_id,connection_factory=connection_factory)
        if principal is None:
            raise LoginFailed()
        limiter.successful(username)
        return principal
    except LoginFailed:
        raise
    except (pymysql.MySQLError,OSError,ValueError):
        raise AuthenticationUnavailable() from None
