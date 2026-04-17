"""
routes.dashboard
================
Main landing page — shows recent invoices and quotations at a glance.
"""
import logging

from flask import render_template

from models import Company, Invoice, Quotation
from routes import main_bp

logger = logging.getLogger(__name__)


@main_bp.route("/")
def dashboard():
    """Render the dashboard with recent activity and quick-action stats."""
    try:
        quotations      = Quotation.query.order_by(Quotation.date.desc()).limit(10).all()
        invoices        = Invoice.query.order_by(Invoice.date.desc()).limit(10).all()
        company         = Company.query.first()
        total_invoices  = Invoice.query.count()
        total_quotations = Quotation.query.count()
    except Exception as exc:
        logger.error("Dashboard load error: %s", exc)
        quotations = invoices = []
        company    = None
        total_invoices = total_quotations = 0

    return render_template(
        "dashboard.html",
        quotations       = quotations,
        invoices         = invoices,
        company          = company,
        total_invoices   = total_invoices,
        total_quotations = total_quotations,
    )
