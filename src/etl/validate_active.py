from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import sys

import xlrd


ROOT = Path(__file__).resolve().parents[2]

ACTIVE_FILE = ROOT / "data" / "raw" / "aktif" / "1.XLS"
REFERENCE_FILE = ROOT / "data" / "raw" / "pendukung" / "SQLRESULT1.XLS"

MONEY_COLUMNS = (
    "jml_pinjaman",
    "saldo_nominatif",
    "tunggakan_pokok",
)

ACTIVE_COLUMNS = {
    "no_rekening",
    "tgl_realisasi",
    "tgl_jatuh_tempo",
    "kolektibilitas",
    "kode_group1",
    "kode_group2",
    *MONEY_COLUMNS,
}

REFERENCE_COLUMNS = {
    "kode_group1",
    "deskripsi_group1",
    "kode_group2",
    "deskripsi_group2",
}

# Pembanding untuk file awal proyek, bukan aturan semua unggahan.
INITIAL_TOTALS = {
    "jml_pinjaman": Decimal("9654562435.00"),
    "saldo_nominatif": Decimal("6497629974.00"),
    "tunggakan_pokok": Decimal("213735116.00"),
}

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def read_xls(path, sheet_name, required_columns, *, verbose=True, file_contents=None):
    if not path.is_file():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    from src.etl.excel_reader import open_book,MAX_CELLS
    book = open_book(path, file_contents)

    if sheet_name not in book.sheet_names():
        raise ValueError(
            f"{path.name}: sheet '{sheet_name}' tidak ditemukan. "
            f"Sheet tersedia: {book.sheet_names()}"
        )

    sheet = book.sheet_by_name(sheet_name)
    if sheet.nrows and len(sheet.row_values(0))*sheet.nrows>MAX_CELLS:
        raise ValueError('Workbook melampaui batas sel pemeriksaan.')

    if sheet.nrows == 0:
        raise ValueError(f"{path.name}: sheet kosong.")

    headers = [
        str(value).strip().lower()
        for value in sheet.row_values(0)
    ]

    duplicates = [
        name for name, count in Counter(headers).items()
        if name and count > 1
    ]

    if duplicates:
        raise ValueError(
            f"{path.name}: nama kolom berulang: {duplicates}"
        )

    missing = required_columns - set(headers)

    if missing:
        raise ValueError(
            f"{path.name}: kolom belum tersedia: {sorted(missing)}"
        )

    rows = []
    blank_rows = 0

    for index in range(1, sheet.nrows):
        cells = sheet.row(index)

        if all(str(cell.value).strip() == "" for cell in cells):
            blank_rows += 1
            continue

        row = {
            name: cells[column]
            for column, name in enumerate(headers)
            if name
        }

        # Nomor baris asli Excel, termasuk baris header.
        rows.append((index + 1, row))

    if verbose:
        print(f"\nFile: {path.name}")
        print(f"Sheet: {sheet_name}")
        print(f"Baris data: {len(rows)}")
        print(f"Kolom: {len(headers)}")
        print(f"Baris kosong dilewati: {blank_rows}")

    if not rows:
        raise ValueError(f"{path.name}: tidak ada baris data.")

    return book, rows


def text_value(cell):
    # Kode dan nomor rekening harus tetap berupa teks.
    # Tidak menebak nol di depan apabila sumbernya numerik.
    if cell.ctype != xlrd.XL_CELL_TEXT:
        raise ValueError("harus berupa teks pada Excel")

    value = str(cell.value).strip()

    if not value:
        raise ValueError("kosong")

    return value


def money_value(cell):
    if cell.ctype not in (xlrd.XL_CELL_NUMBER, xlrd.XL_CELL_TEXT):
        raise ValueError("bukan nominal yang valid")

    raw = str(cell.value).strip()

    # Tidak menebak arti titik/koma pemisah ribuan.
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", raw):
        raise ValueError("format nominal kosong atau ambigu")

    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise ValueError("nominal tidak dapat dibaca")

    if not value.is_finite() or value < 0:
        raise ValueError("nominal negatif atau tidak valid")

    if value != value.quantize(Decimal("0.01")):
        raise ValueError("nominal memiliki lebih dari dua desimal")

    return value


def date_value(cell, datemode):
    if cell.ctype == xlrd.XL_CELL_DATE:
        return xlrd.xldate_as_datetime(cell.value, datemode).date()

    if cell.ctype != xlrd.XL_CELL_TEXT:
        raise ValueError("tanggal bukan teks atau tanggal Excel")

    raw = str(cell.value).strip()

    # Format pada ekspor yang diperiksa: 21-Jul-16.
    match = re.fullmatch(r"(\d{1,2})-([A-Za-z]{3})-(\d{2}|\d{4})", raw)

    if match:
        day, month_text, year_text = match.groups()
        month = MONTHS.get(month_text.lower())

        if month is None:
            raise ValueError("nama bulan tidak dikenali")

        year = int(year_text)

        # Aturan eksplisit untuk tahun dua digit:
        # 00–68 = 2000–2068; 69–99 = 1969–1999.
        if len(year_text) == 2:
            year += 2000 if year <= 68 else 1900

        return date(year, month, int(day))

    # Format alternatif yang tidak ambigu.
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"format tanggal tidak dikenali: {raw!r}")


def rupiah(value):
    formatted = f"{value:,.2f}"
    return "Rp" + formatted.translate(str.maketrans(",.", ".,"))


def main():
    findings = []

    def report(level, source, row, field, message):
        findings.append((level, source, row, field, message))

    print("VALIDASI AWAL DATA PEMBIAYAAN AKTIF")
    print("Tidak menulis ke MySQL dan tidak mengubah Excel.")

    active_book, active_rows = read_xls(
        ACTIVE_FILE, "SQLRESULT", ACTIVE_COLUMNS
    )

    _, reference_rows = read_xls(
        REFERENCE_FILE, "SQLRESULT1", REFERENCE_COLUMNS
    )

    # Membentuk kamus kode -> nama, tanpa menggabungkan baris kontrak.
    mappings = {}

    for code_column, name_column, label in (
        ("kode_group1", "deskripsi_group1", "marketing"),
        ("kode_group2", "deskripsi_group2", "sektor"),
    ):
        candidates = defaultdict(set)

        for row_number, row in reference_rows:
            try:
                code = text_value(row[code_column])
                name = text_value(row[name_column])
                candidates[code].add(name)
            except ValueError as error:
                report(
                    "WARNING", "referensi", row_number,
                    code_column, str(error)
                )

        mapping = {}

        for code, names in candidates.items():
            if len(names) == 1:
                mapping[code] = next(iter(names))
            else:
                report(
                    "WARNING", "referensi", "-",
                    code_column,
                    f"Kode {code!r} memiliki beberapa nama: "
                    f"{sorted(names)}. Tidak dipetakan otomatis."
                )

        mappings[code_column] = mapping

        print(f"\nReferensi {label}:")
        for code, name in sorted(mapping.items()):
            print(f"- {code}: {name}")

    accounts = {}
    totals = {column: Decimal("0") for column in MONEY_COLUMNS}
    invalid_money = Counter()
    collectibility = Counter()
    dates = {"tgl_realisasi": [], "tgl_jatuh_tempo": []}
    unmapped = Counter()

    for row_number, row in active_rows:
        try:
            account = text_value(row["no_rekening"])

            if len(account) > 100:
                raise ValueError("panjang nomor rekening melebihi 100 karakter")

            if account in accounts:
                report(
                    "BLOCKING", "aktif", row_number, "no_rekening",
                    f"Berulang dengan baris Excel {accounts[account]}."
                )
            else:
                accounts[account] = row_number

        except ValueError as error:
            report(
                "BLOCKING", "aktif", row_number,
                "no_rekening", str(error)
            )

        for column in MONEY_COLUMNS:
            try:
                totals[column] += money_value(row[column])
            except ValueError as error:
                invalid_money[column] += 1
                report(
                    "BLOCKING", "aktif", row_number,
                    column, str(error)
                )

        try:
            category = text_value(row["kolektibilitas"]).upper()
        except ValueError:
            category = "UNKNOWN"

        if category not in {"L", "KL", "D", "M"}:
            report(
                "WARNING", "aktif", row_number, "kolektibilitas",
                "Kategori tidak dikenali; NPF belum boleh dinyatakan lengkap."
            )
            category = "UNKNOWN"

        collectibility[category] += 1

        for column in mappings:
            try:
                code = text_value(row[column])
            except ValueError:
                code = ""

            if code not in mappings[column]:
                unmapped[column] += 1
                report(
                    "WARNING", "aktif", row_number, column,
                    "Kode tidak memiliki pemetaan nama yang pasti."
                )

        parsed_dates = {}

        for column in dates:
            try:
                parsed = date_value(row[column], active_book.datemode)
                parsed_dates[column] = parsed
                dates[column].append(parsed)
            except ValueError as error:
                report(
                    "WARNING", "aktif", row_number,
                    column, str(error)
                )

        realization = parsed_dates.get("tgl_realisasi")
        maturity = parsed_dates.get("tgl_jatuh_tempo")

        if realization and maturity and maturity < realization:
            report(
                "WARNING", "aktif", row_number, "tgl_jatuh_tempo",
                "Jatuh tempo lebih awal daripada realisasi."
            )

    print("\nRINGKASAN PEMERIKSAAN")
    print(f"Jumlah baris aktif: {len(active_rows)}")
    print(f"Rekening unik yang terbaca: {len(accounts)}")

    print("\nTotal nominal:")
    for column, total in totals.items():
        if invalid_money[column]:
            print(
                f"- {column}: TOTAL BELUM VALID "
                f"({invalid_money[column]} baris bermasalah)"
            )
        else:
            print(f"- {column}: {rupiah(total)}")
            comparison = (
                "SESUAI" if total == INITIAL_TOTALS[column]
                else "BERBEDA"
            )
            print(f"  Pembanding file awal proyek: {comparison}")

    print("\nJumlah per kolektibilitas:")
    for category in ("L", "KL", "D", "M", "UNKNOWN"):
        print(f"- {category}: {collectibility[category]}")

    print("\nPemetaan nama:")
    print(f"- Marketing belum terpetakan: {unmapped['kode_group1']}")
    print(f"- Sektor belum terpetakan: {unmapped['kode_group2']}")

    print("\nRentang tanggal yang berhasil dibaca:")
    for column, values in dates.items():
        if values:
            print(f"- {column}: {min(values)} s.d. {max(values)}")
        else:
            print(f"- {column}: tidak tersedia")

    report(
        "WARNING", "metadata", "-", "position_date",
        "Tanggal posisi resmi belum dikonfirmasi; tetap NULL. "
        "Tidak diambil otomatis dari tanggal transaksi atau tanggal hari ini."
    )

    counts = Counter(item[0] for item in findings)

    print("\nTEMUAN VALIDASI")
    print(f"BLOCKING: {counts['BLOCKING']}")
    print(f"WARNING: {counts['WARNING']}")

    # Masalah yang menghalangi pemuatan ditampilkan lebih dahulu.
    ordered = sorted(findings, key=lambda item: item[0] != "BLOCKING")

    for level, source, row_number, field, message in ordered[:40]:
        print(
            f"[{level}] {source} | baris {row_number} | "
            f"{field}: {message}"
        )

    if len(findings) > 40:
        print(f"... {len(findings) - 40} temuan lainnya tidak ditampilkan.")

    if counts["BLOCKING"]:
        print("\nHASIL: perlu memperbaiki masalah sebelum pemuatan data.")
        return 1

    print("\nHASIL: pemeriksaan awal tidak menemukan masalah blocking.")
    print("Warning tetap dicatat dan ditinjau sesuai fungsi dashboard.")
    print("Ini belum memvalidasi seluruh kolom atau kelayakan fitur model.")
    print("Belum ada data yang dimasukkan atau dipublikasikan ke MySQL.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (FileNotFoundError, ValueError, xlrd.XLRDError) as error:
        print(f"\nVALIDASI BERHENTI: {error}")
        sys.exit(1)
