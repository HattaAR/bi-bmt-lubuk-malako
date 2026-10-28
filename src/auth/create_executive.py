"""Interactive executive-account creation. Existing active admin credentials required."""

import getpass
import hmac
import sys
import warnings

import pymysql

from src.auth.bootstrap_admin import _InteractiveParser
from src.auth.service import AuthenticationUnavailable, LoginFailed
from src.database.executive_accounts import create_executive


def main(argv=None):
    _InteractiveParser(description="Buat akun pimpinan dengan autentikasi admin; seluruh input interaktif.").parse_args(argv)
    if not sys.stdin.isatty():
        print("Terminal interaktif diperlukan; input pipe/file ditolak.")
        return 1
    admin_password=password=confirmation=None
    try:
        admin_username=input("Username admin: ")
        with warnings.catch_warnings():
            warnings.simplefilter("error",getpass.GetPassWarning)
            admin_password=getpass.getpass("Password admin: ")
            username=input("Username pimpinan baru: ")
            display_name=input("Nama tampilan pimpinan: ")
            password=getpass.getpass("Password baru (minimal 12 karakter): ")
            confirmation=getpass.getpass("Konfirmasi password baru: ")
        if not hmac.compare_digest(password.encode("utf-8"),confirmation.encode("utf-8")):
            print("Konfirmasi tidak cocok; akun tidak dibuat.")
            return 1
        user_id=create_executive(admin_username,admin_password,username,display_name,password)
        print(f"Akun pimpinan dibuat. user_id={user_id}; role=executive; aktif.")
        return 0
    except getpass.GetPassWarning:
        print("Input password tersembunyi tidak tersedia; operasi dibatalkan.")
    except (KeyboardInterrupt,EOFError):
        print("\nOperasi dibatalkan.")
    except LoginFailed as error:
        print(str(error))
    except AuthenticationUnavailable:
        print("Layanan autentikasi sementara tidak tersedia.")
    except PermissionError:
        print("Akun admin aktif diperlukan; akun tidak dibuat.")
    except pymysql.MySQLError as error:
        code=error.args[0] if error.args and isinstance(error.args[0],int) else None
        print(f"Operasi database gagal. Kode MySQL: {code}; pesan driver tidak ditampilkan.")
    except (ValueError,OSError):
        print("Pembuatan akun ditolak; periksa input, duplikasi username, atau konfigurasi.")
    finally:
        admin_password=password=confirmation=None
    return 1


if __name__=="__main__":
    sys.exit(main())
