from __future__ import annotations


class DocuRapiError(Exception):
    """Base exception untuk error bisnis DocuRapi."""


class InvalidDocumentError(DocuRapiError):
    """File dokumen tidak valid."""


class DocumentProcessingError(DocuRapiError):
    """Pemrosesan dokumen gagal."""
