"""Presentation-only metadata and a small shared browser animation controller."""
import hashlib
from html import escape
import json
from pathlib import Path
import streamlit as st
from src.ui.shared.assets import asset_text

from src.ui.shared.paths import ASSETS


def percent_markup(value,final):
    if value is None:return escape(final)
    return (f'<span data-bmt-count="{escape(str(value),quote=True)}" '
            f'data-bmt-final="{escape(final,quote=True)}">'
            f'<span class="bmt-motion-sr">{escape(final)}</span>'
            f'<span aria-hidden="true">{escape(final)}</span></span>')


def motion_scope(result):
    publication=result.get('publication') or result.get('current') or {}
    identity={key:publication.get(key) for key in
              ('publication_id','dataset_version_id','reference_dataset_version_id')}
    source={'publication':identity,'filters':result.get('filters',{}),
            'metric':result.get('metric'),'group_by':result.get('group_by')}
    return hashlib.sha256(json.dumps(source,sort_keys=True,default=str).encode()).hexdigest()[:24]


def scope_attributes(result,page):
    from src.ui.executive.page_runtime import current_route
    route=current_route()
    route_attribute='' if route is None else f' data-bmt-route="{escape(route,quote=True)}"'
    return f'data-bmt-snapshot="{motion_scope(result)}" data-bmt-page="{escape(page,quote=True)}"'+route_attribute


def _javascript():
    script=asset_text(ASSETS/'js/motion.js')
    version=hashlib.sha256(script.encode()).hexdigest()[:12]
    return script.replace('__BMT_MOTION_VERSION__',version)


_RUNTIME=st.components.v2.component('bmt_motion_runtime',html='<span data-bmt-runtime hidden></span>',
                                   js=_javascript(),isolate_styles=False)


def load_motion(page,route=None):
    st.html('<style>'+asset_text(ASSETS/'css/motion.css')+'</style>')
    _RUNTIME(data={'page':page,'route':route},key='bmt_motion_runtime')
