"""
routes
======
HTTP layer for BillGen.  All route modules share a single Flask
Blueprint named ``main`` so that ``url_for('main.<endpoint>')`` works
identically across every template without changes.

Sub-modules are imported at the bottom of this file *after* the Blueprint
is created to avoid circular-import issues — this is the standard Flask
pattern for large-Blueprint applications.

Blueprint prefix: ``/``  (no prefix — all paths are absolute)
"""
from flask import Blueprint

main_bp = Blueprint("main", __name__)

# Import sub-modules AFTER blueprint creation (registers their routes)
from routes import (  # noqa: E402, F401
    customers,
    dashboard,
    gst,
    invoices,
    quotations,
    uploads,
)
