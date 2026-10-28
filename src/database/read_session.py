"""Sequential connection leases confined to one executive page render.

No connection/principal cache: every lease runs fresh SQL and rolls back when
released. The physical connection dies at render end, including rerun/stop.
Nested/concurrent leases and other threads get independent connections.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import threading

_render=ContextVar('bmt_read_render',default=None)


@dataclass
class _Render:
    owner: int
    connection: object=None
    leased: bool=False
    ended: bool=False


class _Lease:
    def __init__(self,render):
        self._render=render
        self._released=False

    def _check(self):
        if self._released or self._render.ended:raise RuntimeError('Connection lease has ended.')
        if self._render.owner!=threading.get_ident():raise RuntimeError('Connection lease belongs to another thread.')

    def __getattr__(self,name):
        self._check()
        value=getattr(self._render.connection,name)
        if not callable(value):return value
        def checked(*args,**kwargs):
            self._check()
            return value(*args,**kwargs)
        return checked

    def __enter__(self):return self

    def __exit__(self,*error):self.close()

    def close(self):
        if self._released:return
        self._check()
        self._released=True
        state=self._render
        try:
            state.connection.rollback()  # Next guard must see a fresh transaction.
        except Exception:
            try:state.connection.close()
            finally:state.connection=None
            raise
        finally:state.leased=False


def checkout(create):
    state=_render.get()
    if state is None or state.ended or state.owner!=threading.get_ident() or state.leased:
        return create()
    if state.connection is None:state.connection=create()
    state.leased=True
    return _Lease(state)


@contextmanager
def read_session():
    state=_Render(threading.get_ident())
    token=_render.set(state)
    try:yield
    finally:
        _render.reset(token)
        state.ended=True
        if state.connection is not None:state.connection.close()
