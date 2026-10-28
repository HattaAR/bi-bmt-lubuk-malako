"""A static destination frame, cleared before any snapshot-backed content paints."""
from contextlib import contextmanager
from contextvars import ContextVar
from html import escape
import streamlit as st

_loading=ContextVar('bmt_loading_frame',default=None)


class _Frame:
    def __init__(self,title,route=None):
        self.route=route
        self.slot=st.empty()
        self.cleared=False
        kind={'Beranda':'home','Kualitas Portofolio':'quality','Konsentrasi Portofolio':'concentration',
              'Portofolio Marketing':'marketing','Analisis Historis':'historical'}.get(title,'simple')
        self.slot.html(f'<section class="bmt-page-loading" data-layout="{kind}" aria-busy="true" '
                       f'aria-label="Memuat {escape(title)}"><header><div class="bmt-loading-breadcrumb">Pimpinan</div>'
                       f'<h1>{escape(title)}</h1><p role="status">Memuat data…</p></header>'
                       '<div class="bmt-loading-filter" aria-hidden="true"></div>'
                       '<div class="bmt-loading-cards" aria-hidden="true"><i></i><i></i><i></i></div>'
                       '<div class="bmt-loading-chart" aria-hidden="true"></div></section>')

    def clear(self):
        if not self.cleared:
            self.cleared=True
            self.slot.empty()


@contextmanager
def loading_frame(title,route=None):
    frame=_Frame(title,route)
    token=_loading.set(frame)
    try:yield
    finally:
        frame.clear()
        _loading.reset(token)


def finish_loading(result=None):
    frame=_loading.get()
    if frame is None:return
    frame.clear()


def current_route():
    frame=_loading.get()
    return frame.route if frame else None
