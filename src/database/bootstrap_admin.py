"""Create the first active admin only. No update, reset, or promotion operations."""

import re

import pymysql

from src.auth.passwords import hash_password
from src.database.active_candidates import active_write_transaction
from src.database.connection import get_connection


class BootstrapError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _validate_identity(username, display_name):
    if not isinstance(username, str) or not isinstance(display_name, str):
        raise BootstrapError("IDENTITY_INVALID", "Username dan nama tampilan harus berupa teks.")
    username, display_name = username.strip(), display_name.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", username):
        raise BootstrapError("IDENTITY_INVALID", "Username 1–100 karakter: huruf Latin, angka, titik, garis bawah, atau tanda minus; diawali huruf/angka.")
    if (not display_name or len(display_name) > 150
            or any(ord(char) < 32 or ord(char) == 127 for char in display_name)):
        raise BootstrapError("IDENTITY_INVALID", "Nama tampilan harus terisi, maksimal 150 karakter, tanpa karakter kontrol.")
    return username, display_name


def _insert_admin_role(cursor, user_id):
    cursor.execute("INSERT INTO app_user_roles(user_id,role_code) VALUES(%s,%s)", (user_id, "admin"))


def bootstrap_first_admin(username, display_name, password, *, connection_factory=get_connection, lock_timeout=10):
    username, display_name = _validate_identity(username, display_name)
    # Expensive hashing runs before acquiring DB locks; no plaintext goes to SQL.
    encoded_hash = hash_password(password)
    try:
        with active_write_transaction(connection_factory=connection_factory, lock_timeout=lock_timeout) as cursor:
            cursor.execute("""SELECT u.user_id FROM app_users u JOIN app_user_roles r USING(user_id)
                WHERE u.is_active=1 AND r.role_code=%s LIMIT 1 FOR UPDATE""", ("admin",))
            if cursor.fetchone() is not None:
                raise BootstrapError("ACTIVE_ADMIN_EXISTS", "Admin aktif sudah tersedia; bootstrap ditolak.")
            cursor.execute("SELECT user_id FROM app_users WHERE username=%s FOR UPDATE", (username,))
            if cursor.fetchone() is not None:
                raise BootstrapError("USERNAME_EXISTS", "Username sudah digunakan; akun existing tidak diubah.")
            cursor.execute("""INSERT INTO app_users(username,password_hash,display_name,is_active)
                VALUES(%s,%s,%s,%s)""", (username, encoded_hash, display_name, True))
            user_id = cursor.lastrowid
            _insert_admin_role(cursor, user_id)
        return user_id
    except pymysql.IntegrityError as error:
        if error.args and error.args[0] == 1062:
            raise BootstrapError("USERNAME_EXISTS", "Username sudah digunakan; akun existing tidak diubah.") from None
        raise
