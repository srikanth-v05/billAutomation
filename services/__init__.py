"""
services — Business logic and third-party integrations.

Each module is framework-agnostic: no Flask imports, no HTTP response
objects.  Routes call services; services call models and utils.

Modules
-------
ai_extraction   Groq LLM + direct Excel parsing for document pre-fill.
invoice_service Create / update Invoice records from validated payload dicts.
excel_service   Excel import (invoices) and workbook builders (GST report,
                invoice upload template).
"""
