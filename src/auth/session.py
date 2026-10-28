"""Per-Streamlit-session context; every guard revalidates database access."""

from dataclasses import dataclass, replace
import secrets
import time

from src.auth.service import AuthenticationUnavailable, Principal, read_principal


SESSION_KEY = "_bmt_authenticated_session"
IDLE_TIMEOUT_SECONDS = 15 * 60
MAX_SESSION_SECONDS = 8 * 60 * 60


class AuthenticationRequired(PermissionError):
    pass


class AccessDenied(PermissionError):
    pass


@dataclass(frozen=True)
class AuthSession:
    user_id: int
    nonce: str
    issued_at: float
    last_activity: float
    roles_snapshot: frozenset[str]  # Change detection only; never authorization.


def logout(state):
    state.clear()


def establish_session(state, principal, *, now=None):
    if not isinstance(principal,Principal):
        raise AuthenticationRequired("Autentikasi diperlukan.")
    now = time.monotonic() if now is None else now
    logout(state)
    state[SESSION_KEY] = AuthSession(principal.user_id,secrets.token_urlsafe(32),now,now,principal.roles)


def require_session(state, *, now=None, touch=True, principal_loader=read_principal):
    now = time.monotonic() if now is None else now
    context = state.get(SESSION_KEY)
    if (not isinstance(context,AuthSession) or now < context.issued_at or now < context.last_activity
            or now-context.last_activity >= IDLE_TIMEOUT_SECONDS or now-context.issued_at >= MAX_SESSION_SECONDS):
        logout(state)
        raise AuthenticationRequired("Silakan masuk kembali.")
    try:
        principal = principal_loader(context.user_id)
    except AuthenticationUnavailable:
        logout(state)
        raise
    if principal is None:
        logout(state)
        raise AuthenticationRequired("Silakan masuk kembali.")
    if principal.roles != context.roles_snapshot:
        logout(state)  # Also clear any role-specific navigation/data/widget context.
    state[SESSION_KEY] = replace(context,roles_snapshot=principal.roles,
                                 last_activity=now if touch else context.last_activity)
    return principal


def require_role(state, role, **kwargs):
    principal = require_session(state,**kwargs)
    if role not in principal.roles:
        context = state[SESSION_KEY]
        logout(state)
        state[SESSION_KEY] = context
        raise AccessDenied("Anda tidak memiliki akses ke area atau tindakan ini.")
    return principal
