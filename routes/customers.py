"""
routes.customers
================
Customer management — CRUD views and the typeahead search API used by
the quotation and invoice forms.

Endpoints
---------
GET  /customers                 List + add-new form
POST /customers                 Create customer
POST /customers/edit/<id>       Update customer
POST /customers/delete/<id>     Delete customer (blocked if linked records exist)
GET  /api/customers?q=<query>   JSON typeahead search (used by JS)
"""
import logging

from flask import flash, jsonify, redirect, render_template, request, url_for

from models import Company, Customer, db
from routes import main_bp

logger = logging.getLogger(__name__)


@main_bp.route("/customers", methods=["GET", "POST"])
def customers():
    """List customers and handle new-customer form submission."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Customer name is required.", "error")
            return redirect(url_for("main.customers"))
        try:
            db.session.add(Customer(
                name    = name,
                address = request.form.get("address", "").strip(),
                gstin   = request.form.get("gstin",   "").strip(),
                state   = request.form.get("state",   "").strip(),
            ))
            db.session.commit()
            flash("Customer added successfully.", "success")
        except Exception as exc:
            logger.error("Add customer error: %s", exc)
            db.session.rollback()
            flash("Error adding customer.", "error")
        return redirect(url_for("main.customers"))

    return render_template(
        "customers.html",
        customers = Customer.query.order_by(Customer.name).all(),
        company   = Company.query.first(),
    )


@main_bp.route("/customers/edit/<int:id>", methods=["POST"])
def edit_customer(id: int):
    """Update an existing customer record."""
    try:
        customer = Customer.query.get_or_404(id)
        name = request.form.get("name", "").strip()
        if not name:
            flash("Customer name is required.", "error")
            return redirect(url_for("main.customers"))
        customer.name    = name
        customer.gstin   = request.form.get("gstin",   "").strip()
        customer.address = request.form.get("address", "").strip()
        customer.state   = request.form.get("state",   "").strip()
        db.session.commit()
        flash("Customer updated successfully.", "success")
    except Exception as exc:
        logger.error("Edit customer %d error: %s", id, exc)
        db.session.rollback()
        flash("Error updating customer.", "error")
    return redirect(url_for("main.customers"))


@main_bp.route("/customers/delete/<int:id>", methods=["POST"])
def delete_customer(id: int):
    """Delete a customer — blocked when linked quotations or invoices exist."""
    try:
        customer = Customer.query.get_or_404(id)
        linked = len(customer.quotations) + len(customer.invoices)
        if linked:
            flash(
                f'Cannot delete "{customer.name}" — '
                f"{linked} linked record(s) exist. Delete those first.",
                "error",
            )
            return redirect(url_for("main.customers"))
        db.session.delete(customer)
        db.session.commit()
        flash("Customer deleted successfully.", "success")
    except Exception as exc:
        logger.error("Delete customer %d error: %s", id, exc)
        db.session.rollback()
        flash("Error deleting customer.", "error")
    return redirect(url_for("main.customers"))


@main_bp.route("/api/customers")
def api_customers():
    """JSON typeahead endpoint — returns up to 10 matching customers.

    Query params:
        q (str): Name substring to search. Returns first 20 if omitted.

    Returns:
        JSON array of customer dicts ``{id, name, address, gstin, state}``.
    """
    try:
        q = request.args.get("q", "").strip()
        rows = (
            Customer.query.filter(Customer.name.ilike(f"%{q}%")).limit(10).all()
            if q
            else Customer.query.limit(20).all()
        )
        return jsonify([c.to_dict() for c in rows])
    except Exception as exc:
        logger.error("Customer search error: %s", exc)
        return jsonify([]), 500
