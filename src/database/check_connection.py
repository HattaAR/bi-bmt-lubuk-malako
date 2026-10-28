import sys

import pymysql

from src.database.connection import get_connection


EXPECTED_TABLES = {
    "app_users",
    "app_user_roles",
    "source_files",
    "dataset_versions",
    "dataset_sources",
    "validation_findings",
    "dataset_publications",
    "current_publications",
    "dim_marketing",
    "dim_sektor",
    "dim_kolektibilitas",
    "dim_tanggal",
    "dim_rekening",
    "fact_pembiayaan_aktif",
}

EXPECTED_CATEGORIES = {
    "L": ("Lancar", 1, 0),
    "KL": ("Kurang Lancar", 2, 1),
    "D": ("Diragukan", 3, 1),
    "M": ("Macet", 4, 1),
    "UNKNOWN": ("Tidak diketahui", 5, None),
}


def main():
    print("Memeriksa koneksi database...", flush=True)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    DATABASE() AS database_name,
                    VERSION() AS server_version,
                    @@port AS server_port
            """)

            info = cursor.fetchone()

            print("\nKONEKSI BERHASIL")
            print(f"Database: {info['database_name']}")
            print(f"Versi: {info['server_version']}")
            print(f"Port: {info['server_port']}")

            cursor.execute("""
                SELECT TABLE_NAME AS table_name, ENGINE AS engine
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """)

            tables = cursor.fetchall()
            found = {row["table_name"] for row in tables}

            print(f"\nJumlah tabel: {len(tables)}")

            for row in tables:
                print(f"- {row['table_name']} ({row['engine']})")

            missing = EXPECTED_TABLES - found

            if missing:
                print("\nTabel yang belum tersedia:")
                for name in sorted(missing):
                    print(f"- {name}")
                return 1

            wrong_engine = [
                row["table_name"]
                for row in tables
                if row["table_name"] in EXPECTED_TABLES
                and (row["engine"] or "").upper() != "INNODB"
            ]

            if wrong_engine:
                print("\nTabel yang belum menggunakan InnoDB:")
                for name in wrong_engine:
                    print(f"- {name}")
                return 1

            cursor.execute("""
                SELECT
                    collectibility_code,
                    collectibility_name,
                    display_order,
                    is_npf_category
                FROM dim_kolektibilitas
                ORDER BY display_order
            """)

            categories = cursor.fetchall()
            actual = {}

            print("\nKategori kolektibilitas:")

            for row in categories:
                code = row["collectibility_code"]

                actual[code] = (
                    row["collectibility_name"],
                    row["display_order"],
                    row["is_npf_category"],
                )

                print(
                    f"- {code}: {row['collectibility_name']} "
                    f"| penanda NPF={row['is_npf_category']}"
                )

            if actual != EXPECTED_CATEGORIES:
                print("\nKategori belum sesuai dengan lima kategori awal.")
                print("Periksa isi tabel dim_kolektibilitas.")
                return 1

            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM fact_pembiayaan_aktif
            """)

            total = cursor.fetchone()["total"]
            print(f"\nJumlah baris pembiayaan aktif: {total}")

            print("\nPemeriksaan berhasil.")
            print("Tidak ada data yang ditambah, diubah, atau dihapus.")
            return 0


if __name__ == "__main__":
    try:
        sys.exit(main())

    except pymysql.MySQLError as error:
        code = error.args[0] if error.args else "tidak diketahui"

        hints = {
            1045: "Periksa DB_USER dan DB_PASSWORD pada .env.",
            1049: "Database belum ditemukan. Periksa DB_NAME.",
            2003: "Pastikan MySQL Laragon aktif dan host/port benar.",
            1146: "Ada tabel yang belum dibuat pada database tujuan.",
            1054: "Struktur kolom belum sesuai dengan SQL sebelumnya.",
        }

        print(f"\nPemeriksaan gagal. Kode MySQL: {code}")
        print(hints.get(code, "Periksa konfigurasi dan struktur database."))
        sys.exit(1)

    except (FileNotFoundError, ValueError) as error:
        print(f"\nKonfigurasi bermasalah: {error}")
        sys.exit(1)