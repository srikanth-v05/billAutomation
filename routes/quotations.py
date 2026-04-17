"""
routes.quotations
=================
Quotation lifecycle — create, view, delete, and convert to invoice.

Endpoints
---------
GET  /quotation/new                  Blank quotation form
POST /quotation/new                  Save new quotation (JSON body)
GET  /quotation/<id>                 View / print quotation
POST /quotation/delete/<id>          Delete quotation
POST /quotation/<id>/to-invoice      Convert to Tax Invoice
GET  /company                        Company settings form
POST /company                        Save company settings
"""
import logging

from flask import flash, jsonify, redirect, render_template, request, url_for

from models import Company, Customer, Quotation, QuotationItem, db
from routes import main_bp
from services import invoice_service
from utils.helpers import get_financial_year, number_to_words

logger = logging.getLogger(__name__)


# ─── Company settings ─────────────────────────────────────────────────────────

@main_bp.route("/company", methods=["GET", "POST"])
def company_settings():
    """View and update company details (name, address, GSTIN, phone)."""
    company = Company.query.first()
    if not company:
        flash("Company record not found. Please contact admin.", "error")
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        name    = request.form.get("name",         "").strip()
        address = request.form.get("address_line_1","").strip()
        state   = request.form.get("state",        "").strip()
        gstin   = request.form.get("gstin",        "").strip()
        phone   = request.form.get("phone",        "").strip()

        if not all([name, address, state, gstin]):
            flash("Name, Address, State and GSTIN are required.", "error")
            return render_template("company_settings.html", company=company)
        try:
            company.name          = name
            company.address_line_1 = address
            company.state         = state
            company.gstin         = gstin
            company.phone         = phone
            db.session.commit()
            flash("Company settings updated successfully.", "success")
            return redirect(url_for("main.dashboard"))
        except Exception as exc:
            logger.error("Update company error: %s", exc)
            db.session.rollback()
            flash("Error updating company settings.", "error")

    return render_template("company_settings.html", company=company)


# ─── Create quotation ─────────────────────────────────────────────────────────

@main_bp.route("/quotation/new", methods=["GET", "POST"])
def create_quotation():
    """Render the new-quotation form (GET) or save a quotation (POST/JSON)."""
    company = Company.query.first()

    if request.method == "POST":
        try:
            data = request.json
            if not data:
                return jsonify({"success": False, "error": "Invalid request data"}), 400

            cdata      = data.get("customer") or {}
            cust_id    = cdata.get("id")
            cust_name  = (cdata.get("name")    or "").strip()
            cust_addr  = (cdata.get("address") or "").strip()
            cust_gst   = (cdata.get("gstin")   or "").strip()
            cust_state = (cdata.get("state")   or "").strip()

            if not cust_name:
                return jsonify({"success": False, "error": "Customer name is required"}), 400

            if cust_id:
                customer = db.session.get(Customer, int(cust_id))
                if not customer:
                    return jsonify({"success": False, "error": "Customer not found"}), 404
                customer.name = cust_name; customer.address = cust_addr
                customer.gstin = cust_gst; customer.state = cust_state
            else:
                customer = Customer(name=cust_name, address=cust_addr,
                                    gstin=cust_gst, state=cust_state)
                db.session.add(customer)
            db.session.flush()

            date_str = (data.get("date") or "").strip()
            if not date_str:
                return jsonify({"success": False, "error": "Date is required"}), 400
            from datetime import datetime
            try:
                q_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"success": False, "error": "Invalid date — use YYYY-MM-DD"}), 400

            prefix   = company.gstin[:2] if company and company.gstin else "34"
            is_intra = bool(cust_gst and cust_gst[:2] == prefix)
            totals   = data.get("totals") or {}

            q_num = f"QT-{int(datetime.utcnow().timestamp())}"
            quot  = Quotation(
                quotation_number = q_num,
                date             = q_date,
                customer_id      = customer.id,
                place_of_supply  = (data.get("place_of_supply") or cust_state),
                total_basic      = float(totals.get("basic",  0)),
                total_gst        = float(totals.get("gst",    0)),
                grand_total      = float(totals.get("grand",  0)),
                percentage_cgst  = 9.0  if is_intra else 0.0,
                percentage_sgst  = 9.0  if is_intra else 0.0,
                percentage_igst  = 0.0  if is_intra else 18.0,
                total_igst       = float(totals.get("igst",   0)),
            )
            db.session.add(quot)
            db.session.flush()

            items = data.get("items") or []
            if not items:
                return jsonify({"success": False, "error": "At least one item is required"}), 400

            for it in items:
                desc = (it.get("description") or "").strip()
                if not desc:
                    continue
                db.session.add(QuotationItem(
                    quotation_id = quot.id,
                    description  = desc,
                    qty          = int(float(it.get("qty",  0))),
                    rate         = float(it.get("rate",  0)),
                    unit         = it.get("unit") or "NOS",
                    gst_rate     = float(it.get("gst_rate", 0)),
                    basic_amount = float(it.get("basic", 0)),
                    gst_amount   = float(it.get("gst",   0)),
                    total_amount = float(it.get("total", 0)),
                ))

            db.session.commit()
            return jsonify({"success": True,
                            "redirect_url": url_for("main.view_quotation", id=quot.id)})

        except ValueError as exc:
            db.session.rollback()
            return jsonify({"success": False, "error": f"Validation: {exc}"}), 400
        except Exception as exc:
            logger.error("Create quotation error: %s", exc)
            db.session.rollback()
            return jsonify({"success": False, "error": str(exc)}), 500

    return render_template("create_quotation.html", company=company)


# ─── View quotation ───────────────────────────────────────────────────────────

@main_bp.route("/quotation/<int:id>")
def view_quotation(id: int):
    """Render the printable quotation view."""
    quotation = Quotation.query.get_or_404(id)
    company   = Company.query.first()
    if not company:
        flash("Company settings not configured.", "error")
        return redirect(url_for("main.dashboard"))

    amount_in_words = number_to_words(round(quotation.grand_total)) + " Only"
    return render_template(
        "view_quotation.html",
        quotation       = quotation,
        company         = company,
        amount_in_words = amount_in_words,
    )


# ─── Delete quotation ─────────────────────────────────────────────────────────

@main_bp.route("/quotation/delete/<int:id>", methods=["POST"])
def delete_quotation(id: int):
    """Delete a quotation — blocked if an invoice has been generated from it."""
    try:
        quotation = Quotation.query.get_or_404(id)
        if quotation.invoice:
            flash(
                f"Cannot delete — quotation has been converted to invoice "
                f"{quotation.invoice.invoice_number}. Delete the invoice first.",
                "error",
            )
            return redirect(url_for("main.view_quotation", id=id))
        db.session.delete(quotation)
        db.session.commit()
        flash("Quotation deleted successfully.", "success")
    except Exception as exc:
        logger.error("Delete quotation %d error: %s", id, exc)
        db.session.rollback()
        flash("Error deleting quotation.", "error")
    return redirect(url_for("main.dashboard"))


# ─── Convert to invoice ───────────────────────────────────────────────────────

@main_bp.route("/quotation/<int:id>/to-invoice", methods=["POST"])
def quotation_to_invoice(id: int):
    """One-click conversion of a quotation into a numbered Tax Invoice."""
    try:
        quotation = Quotation.query.get_or_404(id)
        invoice   = invoice_service.from_quotation(quotation)
        flash(
            f"Invoice {invoice.invoice_number} created from "
            f"quotation {quotation.quotation_number}.",
            "success",
        )
        return redirect(url_for("main.view_invoice", id=invoice.id))
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("main.view_quotation", id=id))
    except Exception as exc:
        logger.error("Quotation→Invoice error: %s", exc)
        db.session.rollback()
        flash("Error converting quotation to invoice.", "error")
        return redirect(url_for("main.view_quotation", id=id))
