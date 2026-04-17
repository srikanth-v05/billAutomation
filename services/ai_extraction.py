"""
services.ai_extraction
======================
Extract structured invoice / bill data from uploaded files.

Supported inputs
----------------
- **PDF**   Text extracted via ``pdfplumber`` → sent to Groq text model.
- **Image** (JPEG / PNG) Base-64 encoded → sent to Groq vision model.
- **Excel** (.xls / .xlsx) Parsed directly via ``openpyxl`` — no LLM needed.

All public functions return a dict matching the schema below, or ``None``
on failure (the caller decides how to surface the error to the user).

Return schema
-------------
::

    {
        "customer": {
            "name": str, "address": str, "gstin": str, "state": str
        },
        "items": [
            {
                "description": str, "qty": int|float,
                "rate": float, "unit": str, "gst_rate": float
            }
        ],
        "date": "YYYY-MM-DD",          # may be empty string if not found
        "place_of_supply": str          # may be empty string
    }
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Optional

from config import Config
from utils.helpers import parse_date, safe_float, safe_int

logger = logging.getLogger(__name__)

# ─── Groq client (lazy singleton) ─────────────────────────────────────────────

_groq_client = None


def _get_groq_client():
    """Return a cached Groq client, or None if the API key is missing."""
    global _groq_client
    if _groq_client is not None:
        return _groq_client
    if not Config.GROQ_API_KEY:
        logger.warning(
            "GROQ_API_KEY not set — AI extraction unavailable. "
            "Add it to your .env file."
        )
        return None
    try:
        from groq import Groq
        _groq_client = Groq(api_key=Config.GROQ_API_KEY)
        logger.info("Groq client initialised.")
    except ImportError:
        logger.error("groq package not installed. Run: pip install groq")
    return _groq_client


# ─── JSON schema sent to the LLM ──────────────────────────────────────────────

_EXTRACTION_SCHEMA = """{
    "customer": {
        "name": "string",
        "address": "string",
        "gstin": "string",
        "state": "string"
    },
    "items": [
        {
            "description": "string",
            "qty": number,
            "rate": number,
            "unit": "string",
            "gst_rate": number
        }
    ],
    "date": "YYYY-MM-DD",
    "place_of_supply": "string"
}"""


# ─── Public entry point ────────────────────────────────────────────────────────

def extract_details_from_file(filepath: str) -> Optional[dict]:
    """Dispatch extraction to the correct handler based on file extension.

    Args:
        filepath: Absolute path to the uploaded file on disk.

    Returns:
        Structured dict matching the extraction schema, or ``None`` on failure.
    """
    logger.info("Extracting details from: %s", filepath)
    ext = filepath.lower()

    if ext.endswith(".pdf"):
        return _extract_pdf(filepath)
    if ext.endswith((".jpg", ".jpeg", ".png")):
        mime = "image/jpeg" if ext.endswith((".jpg", ".jpeg")) else "image/png"
        return _extract_image(filepath, mime)
    if ext.endswith((".xls", ".xlsx")):
        return _extract_excel(filepath)

    logger.error("Unsupported file type: %s", filepath)
    return None


# ─── PDF ──────────────────────────────────────────────────────────────────────

def _extract_pdf(filepath: str) -> Optional[dict]:
    """Extract text from PDF with pdfplumber, then query Groq text model."""
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        logger.error("pdfplumber not installed. Run: pip install pdfplumber")
        return None

    try:
        with pdfplumber.open(filepath) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        logger.error("PDF text extraction failed: %s", exc)
        return None

    if not text.strip():
        logger.error("No text found in PDF: %s", filepath)
        return None

    client = _get_groq_client()
    if client is None:
        return None

    prompt = (
        "Extract invoice/bill details from the text below.\n"
        f"Return ONLY a JSON object matching this schema:\n{_EXTRACTION_SCHEMA}\n"
        "Use null for any field not found. Return ONLY valid JSON.\n\n"
        f"--- DOCUMENT TEXT ---\n{text[:5000]}"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2048,
        )
        raw = response.choices[0].message.content.strip()
        return _parse_json_response(raw)
    except Exception as exc:
        logger.error("Groq API error (PDF): %s", exc)
        return None


# ─── Image ────────────────────────────────────────────────────────────────────

def _extract_image(filepath: str, mime_type: str) -> Optional[dict]:
    """Base-64 encode the image and send to Groq's vision model."""
    client = _get_groq_client()
    if client is None:
        return None

    try:
        with open(filepath, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("utf-8")
    except OSError as exc:
        logger.error("Could not read image file: %s", exc)
        return None

    prompt = (
        "Extract invoice/bill details from this image.\n"
        f"Return ONLY a JSON object matching this schema:\n{_EXTRACTION_SCHEMA}\n"
        "Use null for any field not found. Return ONLY valid JSON."
    )

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{b64}"
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            temperature=0,
            max_tokens=2048,
        )
        raw = response.choices[0].message.content.strip()
        return _parse_json_response(raw)
    except Exception as exc:
        logger.error("Groq API error (image): %s", exc)
        return None


# ─── Excel ────────────────────────────────────────────────────────────────────

def _extract_excel(filepath: str) -> Optional[dict]:
    """Parse an Excel file and return the extraction schema dict.

    Expected columns (same as the invoice upload template):

    ====  =================
    Col   Field
    ====  =================
    A     Invoice No
    B     Date
    C     Customer Name
    D     Customer GSTIN
    E     Customer State
    F     Place of Supply
    G     Item Description
    H     Qty
    I     Rate
    J     Unit
    K     GST Rate (%)
    ====  =================

    Multiple rows with the same Invoice No are merged. The first row's
    customer / date fields populate the quotation header.
    """
    try:
        import openpyxl  # type: ignore
    except ImportError:
        logger.error("openpyxl not installed. Run: pip install openpyxl")
        return None

    try:
        wb = openpyxl.load_workbook(filepath, data_only=True)
        ws = wb.active
    except Exception as exc:
        logger.error("Could not open Excel file: %s", exc)
        return None

    customer: dict = {"name": "", "address": "", "gstin": "", "state": ""}
    place_of_supply = ""
    inv_date = ""
    items: list[dict] = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not any(row):
            continue  # skip blank rows

        # Capture header fields from the first data row only
        if not customer["name"] and row[2]:
            customer["name"]  = str(row[2] or "").strip()
            customer["gstin"] = str(row[3] or "").strip()
            customer["state"] = str(row[4] or "").strip()
            place_of_supply   = str(row[5] or "").strip()
            parsed = parse_date(row[1])
            inv_date = parsed.strftime("%Y-%m-%d") if parsed else ""

        desc = str(row[6] or "").strip()
        if desc:
            items.append({
                "description": desc,
                "qty":      safe_int(row[7],   1),
                "rate":     safe_float(row[8], 0.0),
                "unit":     str(row[9]  or "NOS").strip() or "NOS",
                "gst_rate": safe_float(row[10], 18.0),
            })

    if not customer["name"] and not items:
        logger.error("Excel file appears empty or has no recognisable data")
        return None

    return {
        "customer":        customer,
        "items":           items,
        "date":            inv_date,
        "place_of_supply": place_of_supply,
    }


# ─── JSON response parser ──────────────────────────────────────────────────────

def _parse_json_response(text: str) -> Optional[dict]:
    """Strip markdown fences from an LLM response and parse as JSON.

    Args:
        text: Raw text returned by the LLM.

    Returns:
        Parsed dict, or ``None`` if parsing fails.
    """
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            logger.error("LLM returned non-dict JSON: %s", type(data))
            return None
        return data
    except json.JSONDecodeError as exc:
        logger.error("JSON parse error: %s | raw (first 300 chars): %s", exc, text[:300])
        return None
