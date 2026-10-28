"""Prepare an active candidate without database writes or model execution."""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

import xlrd

from src.etl.validate_active import (
    ACTIVE_COLUMNS, ACTIVE_FILE, MONEY_COLUMNS, REFERENCE_COLUMNS,
    REFERENCE_FILE, date_value, money_value, read_xls, text_value,
)


SCHEMA_VERSION = "active-schema-v1"
MAPPING_VERSION = "active-v1"
VALIDATION_VERSION = "active-validation-v1"
SOURCE_SYSTEM = "BMT"


def fingerprint(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


class CandidateValidationError(ValueError):
    def __init__(self, message, findings=()):
        super().__init__(message)
        self.findings = tuple(findings)


@dataclass(frozen=True)
class Source:
    path: Path
    sheet: str
    sha256: str
    byte_size: int

    def identity(self):
        return {"sha256": self.sha256, "sheet": self.sheet}


@dataclass(frozen=True)
class Finding:
    rule_code: str
    severity: str
    source: str | None
    source_row_number: int | None
    field_name: str | None
    message: str
    affected_function: str


@dataclass
class ActiveRow:
    source_row_number: int
    account_number: str = field(repr=False)
    marketing_code: str | None
    sector_code: str | None
    category: str
    recorded_category: str | None
    money: dict
    realization_date: date | None
    maturity_date: date | None
    contract_duration_days: int | None
    model_input_status: str
    optional: dict


@dataclass
class Candidate:
    active_source: Source
    reference_source: Source
    mapping_version: str
    schema_version: str
    validation_version: str
    ingestion_key: str
    reference_key: str
    marketing: dict
    sectors: dict
    rows: list[ActiveRow] = field(repr=False)
    findings: list[Finding]
    summary: dict
    position_date: date | None = None
    report_metadata: dict | None = None

    def verify_sources(self):
        for source in (self.active_source, self.reference_source):
            if hashlib.sha256(source.path.read_bytes()).hexdigest() != source.sha256:
                raise CandidateValidationError("Sumber berubah setelah validasi; jalankan ulang persiapan.")


def _read_source(path, sheet, columns):
    path = Path(path).resolve()
    contents = path.read_bytes()
    source = Source(path, sheet, hashlib.sha256(contents).hexdigest(), len(contents))
    book, rows = read_xls(path, sheet, columns, verbose=False, file_contents=contents)
    return source, book, rows


def _raw(cell):
    return {"value": cell.value, "excel_type": cell.ctype} if cell is not None else None


def _optional_decimal(cell, precision, scale, nonnegative=False):
    if cell is None or cell.ctype not in (xlrd.XL_CELL_NUMBER, xlrd.XL_CELL_TEXT):
        raise ValueError("missing")
    raw = str(cell.value).strip()
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", raw):
        raise ValueError("format")
    value = Decimal(raw)
    if (not value.is_finite() or abs(value) >= Decimal(10) ** (precision - scale)
            or (nonnegative and value < 0)
            or value != value.quantize(Decimal(1).scaleb(-scale))):
        raise ValueError("range/precision")
    return value


def prepare_candidate(active_path=ACTIVE_FILE, reference_path=REFERENCE_FILE, *,
                      active_sheet="SQLRESULT", reference_sheet="SQLRESULT1",
                      mapping_version=MAPPING_VERSION):
    """Validate both sources and preserve one row per account; no DB access.

    Identifiers accept Excel text only and trim boundary whitespace. Duplicate
    normalized account numbers block the candidate. No leading zeros are added.
    """
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,50}", mapping_version):
        raise CandidateValidationError("Versi pemetaan harus 1–50 karakter ASCII sederhana.")
    active, book, active_rows = _read_source(active_path, active_sheet, ACTIVE_COLUMNS)
    reference, _, reference_rows = _read_source(reference_path, reference_sheet, REFERENCE_COLUMNS)
    findings = []

    def report(rule, severity, source, row, column, message, function="etl_active"):
        findings.append(Finding(rule, severity, source, row, column, message, function))

    mappings = {}
    for code_col, name_col, max_name in (
        ("kode_group1", "deskripsi_group1", 150),
        ("kode_group2", "deskripsi_group2", 200),
    ):
        pairs = defaultdict(set)
        for row_number, row in reference_rows:
            try:
                code, name = text_value(row[code_col]), text_value(row[name_col])
                if len(code) > 30 or len(name) > max_name:
                    raise CandidateValidationError("Kode/nama kamus melebihi kapasitas skema.")
                pairs[code].add(name)
            except CandidateValidationError:
                report("REFERENCE_LENGTH", "blocking", "reference", row_number, code_col,
                       "Kode atau label melampaui kapasitas kolom.")
            except ValueError:
                report("REFERENCE_VALUE_INVALID", "warning", "reference", row_number, code_col,
                       "Pasangan kode/nama bukan teks terisi; tidak digunakan untuk kamus.")
        mapping = {}
        for code, names in pairs.items():
            if len(names) != 1:
                report("REFERENCE_CODE_CONFLICT", "blocking", "reference", None, code_col,
                       "Satu kode memiliki beberapa label; join ambigu ditolak.")
            else:
                mapping[code] = next(iter(names))
        mappings[code_col] = mapping

    accounts, rows = set(), []
    for row_number, raw in active_rows:
        try:
            account = text_value(raw["no_rekening"])
            if len(account) > 100:
                raise ValueError("length")
        except ValueError:
            report("ACCOUNT_INVALID", "blocking", "active", row_number, "no_rekening",
                   "Rekening harus berupa teks terisi dengan panjang maksimal 100.")
            continue
        if account in accounts:
            report("ACCOUNT_DUPLICATE", "blocking", "active", row_number, "no_rekening",
                   "Rekening berulang atau berbenturan setelah pemangkasan spasi.")
        accounts.add(account)

        money = {}
        for column in MONEY_COLUMNS:
            try:
                money[column] = money_value(raw[column])
                if money[column] >= Decimal("1e18"):
                    raise ValueError("capacity")
            except (ValueError, InvalidOperation):
                report("CORE_MONEY_INVALID", "blocking", "active", row_number, column,
                       "Nominal inti kosong, ambigu, negatif, atau melampaui DECIMAL(20,2).")

        codes = {}
        for column, mapping in mappings.items():
            try:
                codes[column] = text_value(raw[column])
                if len(codes[column]) > 30:
                    raise CandidateValidationError("Kode kelompok melebihi 30 karakter.")
            except CandidateValidationError:
                report("GROUP_CODE_LENGTH", "blocking", "active", row_number, column,
                       "Kode kelompok melampaui kapasitas kolom.")
            except ValueError:
                codes[column] = None
            if codes.get(column) not in mapping:
                report("GROUP_UNMAPPED", "warning", "active", row_number, column,
                       "Kode belum terpetakan; kontrak tetap disimpan.", "grouping")

        try:
            recorded_category = text_value(raw["kolektibilitas"])
            if len(recorded_category) > 20:
                raise CandidateValidationError("Kolektibilitas melebihi 20 karakter.")
        except CandidateValidationError:
            report("COLLECTIBILITY_LENGTH", "blocking", "active", row_number, "kolektibilitas",
                   "Kategori sumber melampaui kapasitas kolom.")
            recorded_category = None
        except ValueError:
            recorded_category = None
        category = (recorded_category or "").upper()
        if category not in {"L", "KL", "D", "M"}:
            category = "UNKNOWN"
            report("COLLECTIBILITY_UNKNOWN", "warning", "active", row_number, "kolektibilitas",
                   "Kategori unknown; tidak dianggap Lancar.", "npf")

        dates = {}
        invalid_model = False
        for column in ("tgl_realisasi", "tgl_jatuh_tempo"):
            try:
                value = date_value(raw[column], book.datemode)
                if value.year < 1000:
                    raise ValueError("outside MySQL DATE range")
                dates[column] = value
            except (ValueError, OverflowError, xlrd.XLDateError):
                dates[column] = None
                invalid_model = True
                report("DATE_INVALID", "warning", "active", row_number, column,
                       json.dumps({"reason": "Tanggal tidak valid; analitik NULL", "raw": _raw(raw[column]),
                                   "datemode": book.datemode}, ensure_ascii=False), "duration/model")
        realization, maturity = dates["tgl_realisasi"], dates["tgl_jatuh_tempo"]
        if realization and maturity and maturity < realization:
            invalid_model = True
            maturity = None
            report("MATURITY_BEFORE_REALIZATION", "warning", "active", row_number, "tgl_jatuh_tempo",
                   json.dumps({"reason": "Jatuh tempo mendahului realisasi; jatuh tempo analitik dan durasi NULL",
                               "raw": _raw(raw["tgl_jatuh_tempo"]),
                               "realization_raw": _raw(raw["tgl_realisasi"]), "datemode": book.datemode},
                              ensure_ascii=False), "duration/model")
        duration = (maturity - realization).days if maturity and realization else None
        optional = {}
        for source_col, target_col, precision, scale, nonnegative in (
            ("sisa_margin", "remaining_margin", 20, 2, False),
            ("bi_margin", "recorded_margin", 18, 6, False),
            ("bi_jangka_waktu", "recorded_tenor", 10, 2, True),
        ):
            try:
                optional[target_col] = _optional_decimal(raw.get(source_col), precision, scale, nonnegative)
                if target_col == "recorded_tenor" and optional[target_col] == 0:
                    raise ValueError("zero tenor")
            except (ValueError, InvalidOperation):
                optional[target_col] = None
                invalid_model = True
                report("OPTIONAL_NUMBER_INVALID", "warning", "active", row_number, source_col,
                       json.dumps({"reason": "Atribut opsional tidak valid; disimpan NULL", "raw": _raw(raw.get(source_col))},
                                  ensure_ascii=False), "optional_analytics/model")

        for source_col, target_col, max_len in (
            ("satuan_waktu_angsuran", "installment_unit_code", 20),
            ("akad", "contract_type_code", 30),
            ("jenis_pinjaman", "financing_type_code", 30),
            ("type_pinjaman", "financing_subtype_code", 30),
        ):
            value_cell = raw.get(source_col)
            value = None
            if value_cell is not None and value_cell.ctype == xlrd.XL_CELL_TEXT:
                value = value_cell.value.strip() or None
            elif (source_col == "akad" and value_cell is not None
                  and value_cell.ctype == xlrd.XL_CELL_NUMBER
                  and float(value_cell.value).is_integer()):
                # Existing export stores akad as an integer. No zero-padding.
                value = str(int(value_cell.value))
            if value is not None and len(value) > max_len:
                value = None
            optional[target_col] = value

        rows.append(ActiveRow(row_number, account, codes.get("kode_group1"), codes.get("kode_group2"),
                              category, recorded_category, money, realization, maturity, duration,
                              "ineligible" if invalid_model else "not_checked", optional))

    report("POSITION_DATE_UNKNOWN", "warning", None, None, "position_date",
           "Tanggal posisi tetap NULL/unknown; tren posisi dan pengingat berbasis posisi dibatasi.", "position/trends")
    if any("angsuranke" in raw for _, raw in active_rows):
        report("INSTALLMENT_SEQUENCE_UNVERIFIED", "warning", "active", None, "angsuranke",
               "Kolom sumber tidak digunakan sebagai urutan angsuran atau fitur model; raw tetap pada sumber.", "installment/model")
    margin_cells = [raw.get("tunggakan_basil") for _, raw in active_rows]
    if margin_cells and all(c is not None and str(c.value) in {"0", "0.0"} for c in margin_cells):
        report("MARGIN_ARREARS_ALL_ZERO", "warning", "active", None, "tunggakan_basil",
               "Seluruh nilai sumber nol; bukan bukti tidak ada tunggakan margin dan tidak dipakai sebagai indikator.", "margin_arrears")
    if not active_rows:
        report("ACTIVE_EMPTY", "blocking", "active", None, None, "Sumber aktif tidak memiliki record.")
    if any(f.severity == "blocking" for f in findings):
        raise CandidateValidationError("Validasi wajib gagal; kandidat tidak dimuat.", findings)

    summary = {
        "rows": len(rows), "unique_accounts": len(accounts),
        "totals": {col: sum((row.money[col] for row in rows), Decimal("0.00")) for col in MONEY_COLUMNS},
        "collectibility": dict(Counter(row.category for row in rows)),
        "unmapped_marketing": sum(row.marketing_code not in mappings["kode_group1"] for row in rows),
        "unmapped_sector": sum(row.sector_code not in mappings["kode_group2"] for row in rows),
    }
    identity = {"active": active.identity(), "reference": reference.identity(),
                "mapping": mapping_version, "schema": SCHEMA_VERSION, "validation": VALIDATION_VERSION,
                "source_system": SOURCE_SYSTEM}
    reference_key = fingerprint({"reference": reference.identity(), "mapping": mapping_version,
                                 "schema": SCHEMA_VERSION, "validation": VALIDATION_VERSION})
    return Candidate(active, reference, mapping_version, SCHEMA_VERSION, VALIDATION_VERSION,
                     fingerprint(identity), reference_key, mappings["kode_group1"], mappings["kode_group2"],
                     rows, findings, summary)
