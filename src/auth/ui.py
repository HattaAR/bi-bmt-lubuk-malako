"""Small native Streamlit views over the reusable authentication guards."""

import secrets

import pymysql
import streamlit as st

from src.auth.service import AuthenticationUnavailable, LoginFailed, authenticate
from src.auth.login_presentation import (brand_header,
                                         illustration_panel, load_login_styles)
from src.auth.session import (SESSION_KEY, AccessDenied, AuthenticationRequired, establish_session,
                              logout, require_role, require_session)


def _logout():
    logout(st.session_state)
    st.query_params.clear()


def login_form():
    load_login_styles()
    message = st.session_state.pop("_login_message", None)
    epoch = st.session_state.setdefault("_login_form_epoch", secrets.token_hex(16))
    with st.container(key="bmt_login", gap=None):
        left, right = st.columns(2, gap=None)
        with left, st.container(key="bmt_login_left", gap=None):
            brand_header()
            with st.container(key="bmt_login_form_wrap", gap=None):
                st.title("Masuk ke BI BMT")
                with st.form("login_" + epoch, clear_on_submit=True, border=False):
                    # No user key, URL binding, persistence, or copying of credentials into session state.
                    username = st.text_input("Username", max_chars=100, autocomplete="username",
                                             placeholder="Masukkan username Anda")
                    password = st.text_input("Password", type="password", max_chars=1024,
                                             autocomplete="current-password", placeholder="Masukkan password Anda")
                    submitted = st.form_submit_button("Masuk", type="primary", width="stretch")
                st.html('<p class="bmt-login-account-help">Kesulitan masuk? Hubungi administrator BMT.</p>')
                feedback = st.container(key="bmt_login_feedback", gap=None)
                # Keep the status container mounted even before a message exists.
                feedback.html('<div aria-hidden="true"></div>')
                if message:
                    feedback.error(message)
            st.html('<footer class="bmt-login-panel-footer">'
                    '<span>© 2026 BMT Lubuk Malako</span>'
                    '<span>Sistem Internal</span></footer>')
        with right, st.container(key="bmt_login_right", gap=None):
            illustration_panel()
    if submitted:
        try:
            with feedback, st.spinner("Memeriksa akses…"):
                principal = authenticate(username, password)
        except (LoginFailed, AuthenticationUnavailable) as error:
            logout(st.session_state)
            st.session_state["_login_message"] = str(error)
            st.session_state["_login_form_epoch"] = secrets.token_hex(16)
        else:
            establish_session(st.session_state, principal)
            st.query_params.clear()
        finally:
            password = None
        st.rerun()  # Old form/widget state is removed, including failed submissions.


def entry_principal():
    # An anonymous form rerun is not an expired authenticated session: clearing
    # widget state here would discard the submit trigger before reading it.
    if SESSION_KEY not in st.session_state:
        st.navigation([st.Page(login_form, title="Masuk", default=True)], position="hidden").run()
        return None
    try:
        principal = require_session(st.session_state)
    except (AuthenticationRequired, AuthenticationUnavailable) as error:
        if isinstance(error, AuthenticationUnavailable):
            st.session_state["_login_message"] = str(error)
        st.navigation([st.Page(login_form, title="Masuk", default=True)], position="hidden").run()
        return None
    return principal


def page_guard(role):
    """Guard before rendering content, even when a page is executed directly."""
    try:
        return require_role(st.session_state, role)
    except AuthenticationRequired:
        st.warning("Silakan masuk kembali melalui halaman utama.")
    except AccessDenied:
        st.error("Anda tidak memiliki akses ke area ini.")
    except AuthenticationUnavailable:
        st.error("Layanan autentikasi sementara tidak tersedia.")
    st.stop()


def protected_action(action, *args, **kwargs):
    """Actions perform live authorization; never expose driver/row errors."""
    try:
        result = action(st.session_state, *args, **kwargs)
        from src.ui.executive.page_runtime import finish_loading
        finish_loading(result)
        return result
    except (AuthenticationRequired, AccessDenied):
        st.error("Akses berubah atau sesi berakhir. Buka kembali halaman utama.")
    except AuthenticationUnavailable:
        st.error("Layanan autentikasi sementara tidak tersedia.")
    except (pymysql.MySQLError, OSError, ValueError):
        st.error("Pemeriksaan tidak dapat diselesaikan. Periksa konfigurasi atau sumber melalui CLI lokal.")
    from src.ui.executive.page_runtime import finish_loading
    finish_loading()
    st.stop()
