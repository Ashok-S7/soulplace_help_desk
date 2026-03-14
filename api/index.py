"""
Vercel serverless entry: expose the Flask app so all routes work.
"""
import os
import sys

# Project root = parent of api/ (where app.py and templates live)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_root)
if _root not in sys.path:
    sys.path.insert(0, _root)

from app import app

# Vercel looks for `app` (WSGI app). All requests are rewritten to /api/index.
