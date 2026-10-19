"""Text-only document extraction and deliberately unconfirmed line candidates."""
from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Protocol

from rule_workbench.connectors import _payload

MAX_PAGES = 100
MAX_LINES = 2000
MAX_TEXT = 2_000_000
MAX_CANDIDATES = 100


class RuleExtractor(Protocol):
    """Adapters return draft candidates; mapping and confirmation belong to users."""

    def __call__(self, document: dict) -> list[dict]: ...


def extract_document(name: str, payload: bytes) -> dict:
    _payload(payload)
    name = Path(name).name
    suffix = Path(name).suffix.lower()
    segments = []
    try:
        if suffix in {".md", ".markdown", ".txt"}:
            text = payload.decode("utf-8-sig")
            lines = text.splitlines()
            if len(lines) > MAX_LINES or len(text) > MAX_TEXT:
                raise ValueError("Text documents are limited to 2,000 lines and 2,000,000 characters.")
            segments = [{"text": line, "line": n} for n, line in enumerate(lines, 1) if line.strip()]
        elif suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(payload))
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are unsupported.")
            if len(reader.pages) > MAX_PAGES:
                raise ValueError("PDF documents are limited to 100 pages.")
            total = 0
            for number, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                total += len(text)
                if total > MAX_TEXT:
                    raise ValueError("Extracted PDF text exceeds 2,000,000 characters.")
                if text.strip():
                    segments.append({"text": text, "page": number})
        else:
            raise ValueError("Supported documents: PDF, Markdown, TXT.")
    except ValueError:
        raise
    except Exception:
        raise ValueError("Unable to extract text; verify the document format and encoding.") from None
    if not segments:
        raise ValueError("No text was found. OCR is not supported; provide a text-based document.")
    return {"name": name, "segments": segments}


def candidate_rules(document: dict, extractor: RuleExtractor | None = None) -> list[dict]:
    """Use all nonblank lines as candidates, without claiming semantic extraction.

    Over 100 candidates is an explicit error, so no rule candidates disappear
    silently. An optional callable may supply another local/external adapter;
    this module never makes model or network calls.
    """
    if extractor is not None:
        candidates = extractor(document)
        if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
            raise ValueError("Extractor must return a list of at most 100 candidates.")
        # Preserve adapter content while preventing auto-confirmed imported candidates.
        return [{**rule, "status": "draft"} for rule in candidates]
    candidates = []
    for segment in document["segments"]:
        for offset, line in enumerate(segment["text"].splitlines()):
            if not line.strip():
                continue
            source = {"file": document["name"], "quote": line}
            if "page" in segment:
                source["page"] = segment["page"]
            if "line" in segment:
                source["line"] = segment["line"] + offset
            elif "page" in segment:
                source["line"] = offset + 1
            candidates.append({"id": uuid.uuid4().hex, "text": line, "source": source,
                               "status": "draft", "table": "", "column": "",
                               "kind": "required", "params": {}})
            if len(candidates) > MAX_CANDIDATES:
                raise ValueError("More than 100 candidate lines; split the document before extraction.")
    return candidates
