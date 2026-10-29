"""Scoped presentation tokens; reuse the existing public-asset cache only."""
from src.ui.shared.assets import asset_text
from src.ui.shared.paths import ASSETS


def workspace_css():
    return asset_text(ASSETS/'css/workspace.css')
