"""
Lensetek Playwright Dynamic Web Research Plugin Package
"""

from .scraper import on_load, on_unload, register_tools, fetch_dynamic_webpage

__all__ = ["on_load", "on_unload", "register_tools", "fetch_dynamic_webpage"]
