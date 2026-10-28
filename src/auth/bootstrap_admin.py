"""Interactive operator CLI for creating the first active application admin."""

import argparse
import getpass
import hmac
import sys
import warnings

import pymysql

from src.database.bootstrap_admin import BootstrapError, bootstrap_first_admin


class _InteractiveParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes unrecognized arguments, including secrets.
        self.print_usage(sys.stderr)
        self.exit(2, "Argumen tidak didukung; masukkan identitas dan password lewat prompt interaktif.\n")


def main(argv=None):
    parser = _InteractiveParser(description="Bootstrap admin pertama; semua input diminta secara interaktif.")
    parser.parse_args(argv)  # No username/password flags or positional secrets.
    if not sys.stdin.isatty():
        print("Bootstrap memerlukan terminal interaktif; input dari pipe/file ditolak.")
        return 1
    password = confirmation = None
    try:
        username = input("Username: ")
        display_name = input("Nama tampilan: ")
        with warnings.catch_warnings():
            # getpass normally falls back to echoed input. Abort before that.
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Password (minimal 12 karakter): ")
            confirmation = getpass.getpass("Konfirmasi password: ")
        if not hmac.compare_digest(password.encode("utf-8"), confirmation.encode("utf-8")):
            print("Konfirmasi password tidak cocok; akun tidak dibuat.")
            return 1
        user_id = bootstrap_first_admin(username, display_name, password)
        print(f"Admin pertama berhasil dibuat. user_id={user_id}; role=admin; aktif.")
        return 0
    except getpass.GetPassWarning:
        print("Input password tersembunyi tidak tersedia; bootstrap dibatalkan.")
    except (KeyboardInterrupt, EOFError):
        print("\nBootstrap dibatalkan.")
    except BootstrapError as error:
        print(f"Bootstrap ditolak [{error.code}]: {error}")
    except pymysql.MySQLError as error:
        code = error.args[0] if error.args and isinstance(error.args[0], int) else None
        print(f"Bootstrap gagal. Kode MySQL: {code}. Pesan driver tidak dicetak untuk melindungi data sensitif.")
    except (ValueError, OSError):
        print("Bootstrap gagal; periksa input, konfigurasi, dependensi, atau lock database.")
    finally:
        # Drop these references; Python does not guarantee secure memory erasure.
        password = confirmation = None
    return 1


if __name__ == "__main__":
    sys.exit(main())
