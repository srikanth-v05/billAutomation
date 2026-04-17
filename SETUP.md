# BillGen — Developer Setup Guide

GST billing automation for **SRI VASAVI AGENCIES** (Puducherry).
Generates quotations, tax invoices, and monthly GST filing reports.

---

## Prerequisites

| Requirement | Minimum version |
|---|---|
| Python | 3.10+ |
| TiDB Cloud account | (or any MySQL 8 server) |
| Groq API key | Free tier sufficient |

---

## Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd billAutomation

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and fill in DATABASE_URL, SECRET_KEY, GROQ_API_KEY

# 5. Run the development server
python app.py
# Visit http://localhost:5000
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Flask session signing key — use a long random string |
| `DATABASE_URL` | Yes | MySQL/TiDB connection URI |
| `GROQ_API_KEY` | No* | Groq API key for AI document extraction |

> *AI extraction (PDF/image upload) is disabled if `GROQ_API_KEY` is not set.
> Excel upload and all other features work without it.

---

## Project Structure

```
billAutomation/
│
├── app.py                  # Flask app factory — creates app, registers blueprint,
│                           # ensures DB tables and default company record exist
│
├── config.py               # Config class — reads all settings from environment
├── models.py               # SQLAlchemy ORM models
├── requirements.txt        # Pinned dependencies
├── .env.example            # Environment variable template (copy → .env)
│
├── routes/                 # HTTP layer — one module per domain
│   ├── __init__.py         # Creates main_bp Blueprint; imports sub-modules
│   ├── dashboard.py        # GET  /
│   ├── quotations.py       # /quotation/* + /company
│   ├── invoices.py         # /invoice/* + /invoices
│   ├── customers.py        # /customers/* + /api/customers
│   ├── gst.py              # /gst-report + /gst-report/export
│   └── uploads.py          # /upload + /invoice/upload-excel + /invoice/download-template
│
├── services/               # Business logic — no Flask imports
│   ├── ai_extraction.py    # Groq vision/text + direct Excel parsing
│   ├── invoice_service.py  # Create / update Invoice records; quotation→invoice
│   └── excel_service.py    # Excel import (invoices) + workbook builders
│
├── utils/                  # Pure helpers — no Flask, no DB
│   └── helpers.py          # number_to_words, get_financial_year, safe_int/float…
│
├── static/
│   ├── css/style.css
│   └── js/script.js
│
└── templates/
    ├── base.html
    ├── dashboard.html
    ├── create_quotation.html / view_quotation.html
    ├── create_invoice.html  / view_invoice.html / invoices.html
    ├── gst_report.html
    ├── upload.html          # AI document upload
    ├── upload_invoice.html  # Excel invoice import
    ├── customers.html
    └── company_settings.html
```

### Layer Rules

```
templates  →  routes  →  services  →  models / utils
```

- **Routes** handle HTTP only (parse request, call service, return response).
- **Services** contain all business logic; they import models and utils but never Flask.
- **Utils** are pure Python functions — no side effects, no DB access (except `helpers.get_next_invoice_number` which queries Invoice).

---

## Key Workflows

### 1 — Create an Invoice (3 ways)

| Method | How |
|---|---|
| Manual | Sidebar → New Invoice → fill form → Create Invoice |
| From quotation | View any quotation → **Convert to Invoice** button |
| Excel bulk import | Sidebar → Upload from Excel → upload `.xlsx` matching the template |

### 2 — GST Monthly Report

1. Sidebar → **GST Report**
2. Select month and year → Generate
3. Missing bill numbers in the sequence appear as greyed placeholder rows
4. Click **Export Excel** to download the formatted GSTR-1 summary

### 3 — AI Document Pre-fill

1. Sidebar → **Upload Document**
2. Upload a PDF, image (JPG/PNG), or Excel file
3. Data is extracted and pre-fills the **New Quotation** form for review

---

## Database Models

| Model | Table | Description |
|---|---|---|
| `Company` | `company` | Single company record (SRI VASAVI AGENCIES) |
| `Customer` | `customer` | Bill-to party; linked to quotations and invoices |
| `Quotation` | `quotation` | Pre-sales quotation; optional source for an invoice |
| `QuotationItem` | `quotation_item` | Line items on a quotation |
| `Invoice` | `invoice` | Tax invoice with sequential FY-scoped number |
| `InvoiceItem` | `invoice_item` | Line items with split CGST/SGST/IGST amounts |

### Invoice Numbering

Invoices are numbered per **financial year** (April–March):

```
25-26/001,  25-26/002,  25-26/003, …
```

The integer part (`invoice_number_int`) is used for:
- Gap detection in the GST report
- Duplicate prevention on import

---

## Production Deployment

```bash
# Using gunicorn (installed via requirements.txt)
gunicorn "app:app" --workers 2 --bind 0.0.0.0:8000

# Or with a process manager
gunicorn "app:app" -w 2 -b 0.0.0.0:8000 --access-logfile - --error-logfile -
```

Set `FLASK_DEBUG=0` (or remove it) in your production `.env`.

---

## Adding a New Feature — Checklist

1. **Model change?** → edit `models.py`, let `db.create_all()` handle migration on next start (or use Alembic for production).
2. **Business logic?** → add a function to the relevant `services/` module.
3. **New page?** → add route to the relevant `routes/` module, create template in `templates/`.
4. **New nav link?** → edit `templates/base.html` sidebar.
5. **New JS behaviour?** → add to `static/js/script.js`.
