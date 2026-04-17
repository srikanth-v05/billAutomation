"""
routes.invoices
===============
Full CRUD for Tax Invoices, plus the invoice list page.

Endpoints
---------
GET  /invoices                   Paginated invoice list
GET  /invoice/new                Blank invoice form (auto-assigns next number)
POST /invoice/new                Create invoice (JSON body)
GET  /invoice/<id>               View / print invoice
GET  /invoice/<id>/edit          Pre-filled edit form
POST /invoice/<id>/edit          Update invoice (JSON body)
POST /invoice/delete/<id>        Delete invoice
"""
import logging
from datetime import date

from flask import flash, jsonify, redirect, render_template, request, url_for

from models import Company, Invoice, db
from routes import main_bp
from services import invoice_service
from utils.helpers import get_financial_year, number_to_words

logger = logging.getLogger(__name__)


# ─── List ─────────────────────────────────────────────────────────────────────

@main_bp.route("/invoices")
def invoices():
    """Render the full invoice list, newest first."""
    try:
        all_invoices = (
            Invoice.query
            .order_by(Invoice.date.desc(), Invoice.invoice_number_int.desc())
            .all()
        )
        company = Company.query.first()
    except Exception as exc:
        logger.error("Invoice list error: %s", exc)
        all_invoices, company = [], None

    return render_template("invoices.html", invoices=all_invoices, company=company)


# ─── Create ───────────────────────────────────────────────────────────────────

@main_bp.route("/invoice/new", methods=["GET", "POST"])
def create_invoice():
    """Render the new-invoice form (GET) or save a new invoice (POST/JSON)."""
    company = Company.query.first()

    if request.method == "POST":
        return _handle_save(request, company, existing=None)

    today = date.today()
    fy    = get_financial_year(today)
    next_int, next_num = invoice_service.next_invoice_number(fy)

    return render_template(
        "create_invoice.html",
        company                 = company,
        next_invoice_number     = next_num,
        next_invoice_number_int = next_int,
        editing                 = None,
        extracted               = None,
    )


# ─── View ─────────────────────────────────────────────────────────────────────

@main_bp.route("/invoice/<int:id>")
def view_invoice(id: int):
    """Render the printable Tax Invoice view."""
    invoice = Invoice.query.get_or_404(id)
    company = Company.query.first()
    if not company:
        flash("Company settings not configured.", "error")
        return redirect(url_for("main.invoices"))

    amount_in_words = number_to_words(round(invoice.grand_total)) + " Only"
    return render_template(
        "view_invoice.html",
        invoice         = invoice,
        company         = company,
        amount_in_words = amount_in_words,
    )


# ─── Edit ─────────────────────────────────────────────────────────────────────

@main_bp.route("/invoice/<int:id>/edit", methods=["GET", "POST"])
def edit_invoice(id: int):
    """Pre-fill the invoice form with existing data (GET) or update it (POST/JSON)."""
    company = Company.query.first()
    invoice = Invoice.query.get_or_404(id)

    if request.method == "POST":
        return _handle_save(request, company, existing=invoice)

    editing = {
        "id"                  : invoice.id,
        "invoice_number"      : invoice.invoice_number,
        "invoice_number_int"  : invoice.invoice_number_int,
        "date"                : invoice.date.strftime("%Y-%m-%d"),
        "place_of_supply"     : invoice.place_of_supply or "",
        "customer": {
            "id"     : invoice.customer_id,
            "name"   : invoice.customer.name,
            "address": invoice.customer.address or "",
            "gstin"  : invoice.customer.gstin   or "",
            "state"  : invoice.customer.state   or "",
        },
        "items": [
            {
                "description": item.description,
                "qty"        : item.qty,
                "rate"       : item.rate,
                "unit"       : item.unit,
                "gst_rate"   : item.gst_rate,
            }
            for item in invoice.items
        ],
    }
    return render_template(
        "create_invoice.html",
        company                 = company,
        editing                 = editing,
        next_invoice_number     = invoice.invoice_number,
        next_invoice_number_int = invoice.invoice_number_int,
        extracted               = None,
    )


# ─── Delete ───────────────────────────────────────────────────────────────────

@main_bp.route("/invoice/delete/<int:id>", methods=["POST"])
def delete_invoice(id: int):
    """Permanently delete an invoice."""
    try:
        invoice = Invoice.query.get_or_404(id)
        db.session.delete(invoice)
        db.session.commit()
        flash("Invoice deleted successfully.", "success")
    except Exception as exc:
        logger.error("Delete invoice %d error: %s", id, exc)
        db.session.rollback()
        flash("Error deleting invoice.", "error")
    return redirect(url_for("main.invoices"))


# ─── Shared save handler ──────────────────────────────────────────────────────

def _handle_save(request, company, existing):
    """Parse the JSON body and delegate to invoice_service.save().

    Returns a Flask JSON response so the JS form handler can redirect on success.
    """
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "Invalid request body"}), 400

        prefix  = company.gstin[:2] if company and company.gstin else "34"
        invoice = invoice_service.save(data, prefix, existing=existing)
        return jsonify({
            "success"     : True,
            "redirect_url": url_for("main.view_invoice", id=invoice.id),
        })

    except ValueError as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error("Save invoice error: %s", exc)
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500
