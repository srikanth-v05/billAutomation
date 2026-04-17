"""
routes.gst
==========
GST monthly filing report — view in-browser and export to Excel.

Endpoints
---------
GET  /gst-report                 Report form (defaults to current month)
POST /gst-report                 Regenerate report for selected month/year
GET  /gst-report/export          Download report as .xlsx
"""
import io
import logging
from calendar import monthrange
from datetime import date, datetime

from flask import flash, redirect, render_template, request, send_file, url_for

from models import Company, Invoice
from routes import main_bp
from services import excel_service

logger = logging.getLogger(__name__)


@main_bp.route("/gst-report", methods=["GET", "POST"])
def gst_report():
    """Render the GST monthly report.

    Reads ``month`` and ``year`` from the POST body (form) or GET query
    string, defaulting to the current month.  Fills gaps in bill-number
    sequences with empty placeholder rows.
    """
    company = Company.query.first()
    today   = date.today()

    if request.method == "POST":
        month = int(request.form.get("month", today.month))
        year  = int(request.form.get("year",  today.year))
    else:
        month = int(request.args.get("month", today.month))
        year  = int(request.args.get("year",  today.year))

    from_date = date(year, month, 1)
    to_date   = date(year, month, monthrange(year, month)[1])

    invoices_in_month = (
        Invoice.query
        .filter(Invoice.date >= from_date, Invoice.date <= to_date)
        .order_by(Invoice.invoice_number_int)
        .all()
    )

    # Build report rows with gap detection
    report_rows: list[dict] = []
    totals = {"basic": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0, "total": 0.0}

    if invoices_in_month:
        min_num = invoices_in_month[0].invoice_number_int
        max_num = invoices_in_month[-1].invoice_number_int
        inv_map = {inv.invoice_number_int: inv for inv in invoices_in_month}
        fy      = invoices_in_month[0].financial_year

        for num in range(min_num, max_num + 1):
            if num in inv_map:
                inv = inv_map[num]
                report_rows.append({"empty": False, "invoice": inv})
                totals["basic"] += inv.total_basic
                totals["cgst"]  += inv.total_cgst
                totals["sgst"]  += inv.total_sgst
                totals["igst"]  += inv.total_igst
                totals["total"] += inv.grand_total
            else:
                report_rows.append({
                    "empty"    : True,
                    "number"   : num,
                    "formatted": f"{fy}/{str(num).zfill(3)}",
                })

    months = [(i, datetime(2000, i, 1).strftime("%B")) for i in range(1, 13)]
    years  = list(range(today.year - 3, today.year + 1))

    return render_template(
        "gst_report.html",
        company        = company,
        report_rows    = report_rows,
        totals         = totals,
        selected_month = month,
        selected_year  = year,
        months         = months,
        years          = years,
    )


@main_bp.route("/gst-report/export")
def export_gst_report():
    """Stream the GST report for the requested month as an Excel download."""
    today = date.today()
    month = int(request.args.get("month", today.month))
    year  = int(request.args.get("year",  today.year))

    try:
        wb = excel_service.build_gst_report_workbook(month, year)
    except ImportError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.gst_report", month=month, year=year))

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    fname = datetime(year, month, 1).strftime("GST_Report_%B_%Y.xlsx")
    return send_file(
        output,
        mimetype     = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment = True,
        download_name = fname,
    )
