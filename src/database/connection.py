import os
import ssl
from pathlib import Path

import pymysql
from dotenv import load_dotenv


# Folder utama proyek, tempat file .env berada.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DashboardConnection(pymysql.connections.Connection):
    """Fresh connection/TLS context, preserving the installed driver's policy.

    PyMySQL 1.2.3 PREFERRED creates a CERT_NONE context, but first loads the OS
    root store which that mode cannot use. Skip only that unused I/O. Explicit
    TLS options still go through driver validation; no connection/auth caching.
    Policy equivalence is regression tested against the installed driver.
    """
    def _create_ssl_ctx(self,options):
        if pymysql.VERSION_STRING == '1.2.3' and isinstance(options,dict) and not options:
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname=False
            context.verify_mode=ssl.CERT_NONE
            context.verify_flags|=getattr(ssl,'VERIFY_X509_PARTIAL_CHAIN',0)
            context.verify_flags&=~ssl.VERIFY_X509_STRICT
            context.options|=ssl.OP_NO_SSLv2|ssl.OP_NO_SSLv3
            return context
        return super()._create_ssl_ctx(options)


def _configured_tls_context():
    """Opt-in verified TLS; invalid CA/hostname must fail, never downgrade.

    No CA configured retains the existing local driver's PREFERRED policy,
    which does NOT verify certificates/hostname. Do not describe it as verified.
    Each configured context is fresh and bypasses the default-only optimization.
    """
    ca_file = os.getenv('DB_SSL_CA', '').strip()
    if not ca_file:
        return None
    return ssl.create_default_context(cafile=ca_file)


def get_connection(*, database=None):
    if database is not None:
        return _new_connection(database=database)
    from src.database.read_session import checkout
    return checkout(lambda: _new_connection(database=None))


def _new_connection(*, database=None):
    env_file = PROJECT_ROOT / ".env"

    if not env_file.is_file():
        raise FileNotFoundError(
            f"File .env tidak ditemukan di: {env_file}"
        )

    load_dotenv(dotenv_path=env_file, override=False)

    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER"]

    missing = [
        name for name in required
        if not os.getenv(name)
    ]

    if missing:
        raise ValueError(
            "Konfigurasi .env belum lengkap: " + ", ".join(missing)
        )

    try:
        port = int(os.environ["DB_PORT"])
    except ValueError:
        raise ValueError("DB_PORT harus berupa angka, misalnya 3306.")

    return DashboardConnection(
        host=os.environ["DB_HOST"],
        port=port,
        user=os.environ["DB_USER"],
        password=os.getenv("DB_PASSWORD", ""),
        ssl=_configured_tls_context(),
        database=database if database is not None else os.environ["DB_NAME"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30,
        autocommit=False,
        init_command="SET SESSION time_zone = '+00:00'",
    )
