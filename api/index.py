"""
Vercel serverless entry: expose the Flask app so all routes (e.g. /soulplace/links, /soulplace/table) work.
"""
import os
import sys

# Project root = parent of api/ (where app.py and templates live)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from app import app

# Vercel looks for an `app` (WSGI app) or `handler` in the entry file.
# All requests are sent here via vercel.json rewrites, and Flask handles the path.
