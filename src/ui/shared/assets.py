"""Bounded, versioned cache for public presentation files only."""
import base64
from functools import lru_cache
from pathlib import Path

from src.ui.shared.paths import ASSETS


def _identity(path):
    path=Path(path).resolve()
    if not path.is_relative_to(ASSETS.resolve()):raise ValueError('Only public assets may be cached.')
    stat=path.stat()
    return str(path),stat.st_mtime_ns,stat.st_size


@lru_cache(maxsize=128)
def _bytes(path,modified,size):
    return Path(path).read_bytes()


def asset_text(path):return _bytes(*_identity(path)).decode('utf-8-sig')


@lru_cache(maxsize=32)
def _uri(path,modified,size,media):
    return 'data:'+media+';base64,'+base64.b64encode(_bytes(path,modified,size)).decode('ascii')


def asset_uri(path,media):return _uri(*_identity(path),media)
