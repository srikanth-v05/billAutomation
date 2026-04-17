"""
routes.uploads
==============
File-upload endpoints for two different use-cases:

1. **AI document upload** (``/upload``)
   User uploads a PDF, image, or Excel file containing an existing
   bill/invoice.  The file is parsed (via Groq AI or direct Excel
   parsing) and the extracted data pre-fills the quotation form.

2. **Invoice Excel import** (``/invoice/upload-excel``)
   User uploads an Excel file that follows the import template.
   Rows are bulk-imported as Invoice records (create or update).

3. **Template download** (``/invoice/download-template``)
   Serves the blank import template so the user knows the expected format.

Allowed file types (AI upload): PDF, PNG, JPG, JPEG, XLS, XLSX
Allowed file types (Excel import): XLS, XLSX
Max upload size: 10 MB
"""
import io
import logging
import os

from flask import (
    current_app, flash, redirect, render_template,
    request, send_file, url_for,
)
from werkzeug.utils import secure_filename

from models import Company
from routes import main_bp
from services import ai_extraction, excel_service

logger = logging.getLogger(__name__)

_ALLOWED_DOC  = {"pdf", "png", "jpg", "jpeg", "xls", "xlsx"}
_ALLOWED_XLSX = {"xls", "xlsx"}
_MAX_BYTES    = 10 * 1024 * 1024   # 10 MB


def _extension(filename: str) -> str:
    """Return the lowercase file extension without the leading dot."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _save_upload(file) -> str | None:
    """Validate and save the uploaded file; return the full path or None."""
    if not file or not file.filename:
        flash("No file selected.", "error")
        return None

    ext = _extension(file.filename)
    if ext not in _ALLOWED_DOC:
        flash(
            f"Unsupported file type '.{ext}'. "
            "Allowed: PDF, PNG, JPG, JPEG, XLS, XLSX.",
            "error",
        )
        return None

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > _MAX_BYTES:
        flash("File too large. Maximum size is 10 MB.", "error")
        return None

    filename = secure_filename(file.filename)
    if not filename:
        flash("Invalid filename.", "error")
        return None

    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(path)
    return path


# ─── AI document upload (quotation pre-fill) ──────────────────────────────────

@main_bp.route("/upload", methods=["GET", "POST"])
def upload_file():
    """Upload a document and extract its data to pre-fill the quotation form.

    Supported formats
    -----------------
    - **PDF / Image**  Sent to Groq AI for extraction.
    - **Excel**        Parsed directly via openpyxl (no AI required).

    On success the user is redirected to ``create_quotation`` with the
    extracted data pre-populated.
    """
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file part in the request.", "error")
            return redirect(request.url)

        filepath = _save_upload(request.files["file"])
        if filepath is None:
            return redirect(request.url)

        try:
            extracted = ai_extraction.extract_details_from_file(filepath)
            if extracted is None:
                flash(
                    "Could not extract data from the file. "
                    "Check that GROQ_API_KEY is set and try again.",
                    "error",
                )
                return redirect(request.url)

            company = Company.query.first()
            return render_template(
                "create_quotation.html",
                company  = company,
                extracted = extracted,
            )
        except Exception as exc:
            logger.error("File extraction error: %s", exc)
            flash("Error processing file. Please try again.", "error")
            return redirect(request.url)
        finally:
            try:
                os.remove(filepath)
            except OSError:
                pass

    return render_template("upload.html")


# ─── Invoice Excel import ──────────────────────────────────────────────────────

@main_bp.route("/invoice/upload-excel", methods=["GET", "POST"])
def upload_invoice_excel():
    """Bulk-import invoices from an Excel file.

    Rows with the same Invoice No (within the same financial year) are
    treated as an **update** to the existing record.  New numbers create
    new invoices.  See the downloadable template for the expected format.
    """
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file uploaded.", "error")
            return redirect(request.url)

        file = request.files["file"]
        ext  = _extension(file.filename or "")
        if ext not in _ALLOWED_XLSX:
            flash("Only Excel (.xlsx / .xls) files are accepted here.", "error")
            return redirect(request.url)

        filepath = _save_upload(file)
        if filepath is None:
            return redirect(request.url)

        try:
            result = excel_service.import_invoices(filepath)
            flash(
                f"Import complete — "
                f"{result['created']} created, "
                f"{result['updated']} updated, "
                f"{result['skipped']} skipped.",
                "success",
            )
            return redirect(url_for("main.invoices"))
        except ImportError as exc:
            flash(str(exc), "error")
        except Exception as exc:
            logger.error("Excel import error: %s", exc)
            flash(f"Error processing Excel: {exc}", "error")
        finally:
            try:
                os.remove(filepath)
            except OSError:
                pass
        return redirect(request.url)

    return render_template("upload_invoice.html")


# ─── Template download ────────────────────────────────────────────────────────

@main_bp.route("/invoice/download-template")
def download_invoice_template():
    """Stream the blank invoice upload template as an Excel download."""
    try:
        wb = excel_service.build_upload_template_workbook()
    except ImportError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.upload_invoice_excel"))

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(
        output,
        mimetype      = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment = True,
        download_name = "invoice_upload_template.xlsx",
    )
