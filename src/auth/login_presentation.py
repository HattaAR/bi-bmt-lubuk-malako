"""Local presentation assets for the referensi desain UI; no portfolio access."""

import base64
from pathlib import Path

import streamlit as st
from src.ui.assets import asset_text,asset_uri


ASSETS = Path(__file__).resolve().parents[2] / "assets"


def _data_uri(path, media_type):
    return asset_uri(path,media_type)


def load_login_styles():
    css=asset_text(ASSETS/'css/login.css')
    for token, filename in (("__INTER_FONT__", "Inter-latin.woff2"),
                            ("__JAKARTA_FONT__", "PlusJakartaSans-latin.woff2")):
        css = css.replace(token, _data_uri(ASSETS / "fonts" / filename, "font/woff2"))
    st.html("<style>" + css + "</style>")


def brand_header():
    logo = _data_uri(ASSETS / "logo.png", "image/png")
    st.html(f'<div class="bmt-login-brand"><img src="{logo}" alt="Logo BMT El-Itqan" '
            'width="44" height="44"><div><strong>BI BMT Lubuk Malako</strong>'
            '</div></div>')


def illustration_panel():
    # Geometry is illustrative and deliberately independent of any dataset or KPI.
    st.html(asset_text(ASSETS/'login/illustration.html'))
