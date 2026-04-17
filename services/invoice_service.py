"""
services.invoice_service
========================
Business logic for creating and updating Invoice records.

This module is **framework-agnostic** — it contains no Flask imports, no
``jsonify``, and no ``request`` objects.  Routes validate the HTTP layer,
then delegate here for all DB work.

Typical usage (in a route)
--------------------------
::

    from services import invoice_service

    try:
        invoice = invoice_service.save(payload, company_gstin_prefix)
        return jsonify({"success": True, ...})
    except ValueError as exc:          # validation failure → 400
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:           # unexpected error   → 500
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from models import Customer, Invoice, InvoiceItem, db
from utils.helpers import get_financial_year, safe_float, safe_int

logger = logging.getLogger(__name__)


# ─── Invoice numbering ────────────────────────────────────────────────────────

def next_invoice_number(financial_year: str) -> tuple[int, str]:
    """Return ``(next_int, formatted_string)`` for the given financial year.

    Queries the highest existing ``invoice_number_int`` in *financial_year*
    and increments it.  If no invoices exist yet, starts at 1.

    Args:
        financial_year: FY string such as ``'24-25'``.

    Returns:
        Tuple of ``(int, str)`` e.g. ``(3, '24-25/003')``.
    """
    last = (
        Invoice.query
        .filter_by(financial_year=financial_year)
        .order_by(Invoice.invoice_number_int.desc())
        .first()
    )
    n = (last.invoice_number_int + 1) if last else 1
    return n, f"{financial_year}/{str(n).zfill(3)}"


# ─── Core save function ───────────────────────────────────────────────────────

def save(
    payload: dict,
    company_gstin_prefix: str,
    existing: Optional[Invoice] = None,
) -> Invoice:
    """Create a new Invoice or update *existing* from a validated payload dict.

    The payload shape mirrors the JSON body sent by the invoice form:

    .. code-block:: json

        {
            "date": "YYYY-MM-DD",
            "place_of_supply": "...",
            "invoice_number_int": 5,          // optional override
            "customer": {
                "id": 12,                     // optional; omit to create new
                "name": "...", "address": "...",
                "gstin": "...", "state": "..."
            },
            "items": [
                {
                    "description": "...", "qty": 2, "rate": 500.0,
                    "unit": "NOS", "gst_rate": 18,
                    "basic": 1000.0, "gst": 180.0, "total": 1180.0
                }
            ],
            "totals": {
                "basic": 1000.0, "gst": 180.0, "grand": 1180.0
            }
        }

    Args:
        payload:              Parsed JSON dict from the request body.
        company_gstin_prefix: First two digits of the company GSTIN (e.g. ``'34'``).
        existing:             Pass an :class:`~models.Invoice` instance to
                              update it in place; ``None`` creates a new one.

    Returns:
        The committed :class:`~models.Invoice` instance.

    Raises:
        ValueError: For any validation failure (missing fields, duplicate
                    invoice number, etc.).
        Exception:  Re-raised for unexpected DB errors; caller should rollback.
    """
    # ── Customer ─────────────────────────────────────────────────────────────
    cdata      = payload.get("customer") or {}
    cust_id    = cdata.get("id")
    cust_name  = (cdata.get("name")    or "").strip()
    cust_addr  = (cdata.get("address") or "").strip()
    cust_gst   = (cdata.get("gstin")   or "").strip()
    cust_state = (cdata.get("state")   or "").strip()

    if not cust_name:
        raise ValueError("Customer name is required.")

    if cust_id:
        customer = db.session.get(Customer, int(cust_id))
        if not customer:
            raise ValueError(f"Customer id={cust_id} not found.")
        customer.name    = cust_name
        customer.address = cust_addr
        customer.gstin   = cust_gst
        customer.state   = cust_state
    else:
        customer = Customer(
            name=cust_name, address=cust_addr,
            gstin=cust_gst, state=cust_state,
        )
        db.session.add(customer)
    db.session.flush()  # populate customer.id before using it below

    # ── Date ─────────────────────────────────────────────────────────────────
    date_str = (payload.get("date") or "").strip()
    if not date_str:
        raise ValueError("Invoice date is required.")
    try:
        from datetime import datetime
        inv_date: date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Invalid date format — expected YYYY-MM-DD.")

    # ── Tax type (intra / inter state) ────────────────────────────────────────
    is_intra = bool(cust_gst and cust_gst[:2] == company_gstin_prefix)
    pct_cgst = 9.0  if is_intra else 0.0
    pct_sgst = 9.0  if is_intra else 0.0
    pct_igst = 0.0  if is_intra else 18.0

    # ── Totals ────────────────────────────────────────────────────────────────
    totals      = payload.get("totals") or {}
    total_basic = safe_float(totals.get("basic"), 0.0)
    total_gst   = safe_float(totals.get("gst"),   0.0)
    grand_total = safe_float(totals.get("grand"),  0.0)
    total_cgst  = round(total_gst / 2, 2) if is_intra else 0.0
    total_sgst  = round(total_gst / 2, 2) if is_intra else 0.0
    total_igst  = total_gst if not is_intra else 0.0

    # ── Financial year + invoice number ──────────────────────────────────────
    fy = get_financial_year(inv_date)

    if existing:
        inv_num_int = existing.invoice_number_int
        inv_num_str = existing.invoice_number
    else:
        raw_int = payload.get("invoice_number_int")
        raw_str = (payload.get("invoice_number") or "").strip()
        if raw_int:
            inv_num_int = int(raw_int)
            inv_num_str = raw_str or f"{fy}/{str(inv_num_int).zfill(3)}"
        else:
            inv_num_int, inv_num_str = next_invoice_number(fy)

        # Guard against duplicates in the same FY
        conflict = Invoice.query.filter_by(
            invoice_number_int=inv_num_int, financial_year=fy
        ).first()
        if conflict:
            raise ValueError(
                f"Invoice {inv_num_str} already exists for FY {fy}. "
                "Choose a different number or edit the existing invoice."
            )

    # ── Items ─────────────────────────────────────────────────────────────────
    items_payload = payload.get("items") or []
    if not items_payload:
        raise ValueError("At least one line item is required.")

    # ── Persist ───────────────────────────────────────────────────────────────
    if existing:
        # Update header fields
        existing.date            = inv_date
        existing.financial_year  = fy
        existing.customer_id     = customer.id
        existing.place_of_supply = (payload.get("place_of_supply") or cust_state)
        existing.total_basic     = total_basic
        existing.total_gst       = total_gst
        existing.total_cgst      = total_cgst
        existing.total_sgst      = total_sgst
        existing.total_igst      = total_igst
        existing.grand_total     = grand_total
        existing.percentage_cgst = pct_cgst
        existing.percentage_sgst = pct_sgst
        existing.percentage_igst = pct_igst
        existing.is_intra_state  = is_intra
        # Replace all line items
        InvoiceItem.query.filter_by(invoice_id=existing.id).delete()
        invoice = existing
    else:
        invoice = Invoice(
            invoice_number     = inv_num_str,
            invoice_number_int = inv_num_int,
            date               = inv_date,
            financial_year     = fy,
            customer_id        = customer.id,
            place_of_supply    = (payload.get("place_of_supply") or cust_state),
            total_basic        = total_basic,
            total_gst          = total_gst,
            total_cgst         = total_cgst,
            total_sgst         = total_sgst,
            total_igst         = total_igst,
            grand_total        = grand_total,
            percentage_cgst    = pct_cgst,
            percentage_sgst    = pct_sgst,
            percentage_igst    = pct_igst,
            is_intra_state     = is_intra,
        )
        db.session.add(invoice)
        db.session.flush()

    # Add line items
    for item in items_payload:
        desc = (item.get("description") or "").strip()
        if not desc:
            continue
        basic = safe_float(item.get("basic"), 0.0)
        gst   = safe_float(item.get("gst"),   0.0)
        db.session.add(InvoiceItem(
            invoice_id   = invoice.id,
            description  = desc,
            qty          = safe_int(item.get("qty"),   1),
            rate         = safe_float(item.get("rate"), 0.0),
            unit         = (item.get("unit") or "NOS"),
            gst_rate     = safe_float(item.get("gst_rate"), 0.0),
            basic_amount = basic,
            cgst_amount  = round(gst / 2, 2) if is_intra else 0.0,
            sgst_amount  = round(gst / 2, 2) if is_intra else 0.0,
            igst_amount  = gst if not is_intra else 0.0,
            gst_amount   = gst,
            total_amount = safe_float(item.get("total"), 0.0),
        ))

    db.session.commit()
    logger.info("Invoice %s saved (id=%s).", invoice.invoice_number, invoice.id)
    return invoice


# ─── Quotation → Invoice conversion ──────────────────────────────────────────

def from_quotation(quotation) -> Invoice:
    """Convert a :class:`~models.Quotation` into a new :class:`~models.Invoice`.

    All items, tax rates, and customer details are copied across.  The new
    invoice is auto-numbered within the quotation's financial year.

    Args:
        quotation: A :class:`~models.Quotation` ORM instance.

    Returns:
        The newly committed :class:`~models.Invoice`.

    Raises:
        ValueError: If the quotation has already been converted.
    """
    if quotation.invoice:
        raise ValueError(
            f"Quotation {quotation.quotation_number} has already been converted "
            f"to invoice {quotation.invoice.invoice_number}."
        )

    fy               = get_financial_year(quotation.date)
    inv_num_int, inv_num_str = next_invoice_number(fy)
    is_intra         = quotation.percentage_cgst > 0

    invoice = Invoice(
        invoice_number     = inv_num_str,
        invoice_number_int = inv_num_int,
        date               = quotation.date,
        financial_year     = fy,
        customer_id        = quotation.customer_id,
        quotation_id       = quotation.id,
        place_of_supply    = quotation.place_of_supply,
        is_intra_state     = is_intra,
        total_basic        = quotation.total_basic,
        total_gst          = quotation.total_gst,
        total_cgst         = round(quotation.total_gst / 2, 2) if is_intra else 0.0,
        total_sgst         = round(quotation.total_gst / 2, 2) if is_intra else 0.0,
        total_igst         = quotation.total_igst,
        grand_total        = quotation.grand_total,
        percentage_cgst    = quotation.percentage_cgst,
        percentage_sgst    = quotation.percentage_sgst,
        percentage_igst    = quotation.percentage_igst,
    )
    db.session.add(invoice)
    db.session.flush()

    for item in quotation.items:
        gst = item.gst_amount
        db.session.add(InvoiceItem(
            invoice_id   = invoice.id,
            description  = item.description,
            qty          = item.qty,
            rate         = item.rate,
            unit         = item.unit,
            gst_rate     = item.gst_rate,
            basic_amount = item.basic_amount,
            cgst_amount  = round(gst / 2, 2) if is_intra else 0.0,
            sgst_amount  = round(gst / 2, 2) if is_intra else 0.0,
            igst_amount  = gst if not is_intra else 0.0,
            gst_amount   = gst,
            total_amount = item.total_amount,
        ))

    db.session.commit()
    logger.info(
        "Quotation %s converted to invoice %s.",
        quotation.quotation_number, inv_num_str,
    )
    return invoice
