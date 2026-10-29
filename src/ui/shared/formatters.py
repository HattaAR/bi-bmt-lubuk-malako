"""Unchanged Indonesian numeric presentation used by both roles."""
from decimal import Decimal

def number(value, places=0):
    return "—" if value is None else f"{value:,.{places}f}".translate(str.maketrans({",": ".", ".": ","}))


def rupiah(value):
    return "—" if value is None else "Rp" + number(value, 2)


def compact_rupiah(value):
    if value is None:
        return "—"
    for scale, label in ((Decimal('1000000000000'), 'triliun'), (Decimal('1000000000'), 'miliar'), (Decimal('1000000'), 'juta')):
        if abs(value) >= scale:
            return 'Rp' + number(value / scale, 2) + ' ' + label
    return rupiah(value)


def percent(value):
    return "—" if value is None else number(value, 2) + "%"

