"""
Vercel serverless entry: expose the Flask app so all routes work.
Rewrite sends original path as ?__path=/soulplace/... so we fix PATH_INFO before calling Flask.
"""
import os
import sys
from urllib.parse import parse_qs, unquote

# Project root = parent of api/ (where app.py and templates live)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_root)
if _root not in sys.path:
    sys.path.insert(0, _root)

from app import app as flask_app


def app(environ, start_response):
    """WSGI wrapper: fix PATH_INFO when Vercel rewrite sends original path in __path query."""
    path_info = environ.get("PATH_INFO", "") or "/"
    qs = environ.get("QUERY_STRING", "") or ""
    path_was_set = False
    if qs and "__path=" in qs:
        try:
            params = parse_qs(qs, keep_blank_values=True)
            if "__path" in params and params["__path"]:
                path = params["__path"][0]
                path = (unquote(path).split("?")[0] or "/").strip().rstrip("/") or "/"
                environ["PATH_INFO"] = path
                path_was_set = True
                parts = [p for p in qs.split("&") if not p.startswith("__path=")]
                environ["QUERY_STRING"] = "&".join(parts)
        except Exception:
            pass
    # Only fallback when we did NOT set path from __path (direct hit on /api/index)
    if not path_was_set and path_info.strip("/") in ("api", "api/index"):
        environ["PATH_INFO"] = "/soulplace/"
    return flask_app(environ, start_response)
