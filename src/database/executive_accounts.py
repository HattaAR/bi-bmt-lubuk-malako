"""Create an executive-only account after authenticating an existing admin."""

import pymysql

from src.auth.passwords import hash_password
from src.auth.service import authenticate
from src.auth.session import AccessDenied
from src.auth.throttle import DEFAULT_LIMITER
from src.database.active_candidates import active_write_transaction
from src.database.bootstrap_admin import _validate_identity
from src.database.connection import get_connection
from src.database.publication_checks import PublicationError, require_admin


class AccountCreationError(ValueError):
    pass


def _insert_executive_role(cursor,user_id):
    cursor.execute("INSERT INTO app_user_roles(user_id,role_code) VALUES(%s,%s)",(user_id,"executive"))


def create_executive(admin_username,admin_password,username,display_name,password,*,
                     connection_factory=None,limiter=DEFAULT_LIMITER):
    factory=connection_factory or get_connection
    actor=authenticate(admin_username,admin_password,connection_factory=factory,limiter=limiter)
    if "admin" not in actor.roles:
        raise AccessDenied("Autentikasi admin aktif diperlukan.")
    username,display_name=_validate_identity(username,display_name)
    encoded=hash_password(password)
    try:
        with active_write_transaction(connection_factory=factory) as cursor:
            try:
                require_admin(cursor,actor.user_id,lock=True)
            except PublicationError:
                raise AccessDenied("Autentikasi admin aktif diperlukan.") from None
            cursor.execute("SELECT user_id FROM app_users WHERE username=%s FOR UPDATE",(username,))
            if cursor.fetchone() is not None:
                raise AccountCreationError("Username sudah digunakan; akun existing tidak diubah.")
            cursor.execute("INSERT INTO app_users(username,password_hash,display_name,is_active) VALUES(%s,%s,%s,%s)",
                           (username,encoded,display_name,True))
            user_id=cursor.lastrowid
            _insert_executive_role(cursor,user_id)
        return user_id
    except pymysql.IntegrityError as error:
        if error.args and error.args[0]==1062:
            raise AccountCreationError("Username sudah digunakan; akun existing tidak diubah.") from None
        raise
