from __future__ import annotations

import os
import fitz
from PIL import Image
import io

class PDFToImageConverter:
    """
    Handles converting PDF pages to high-resolution images for precision cropping.
    Uses PyMuPDF (fitz) to avoid Poppler dependency.
    """
    _cached_path: str | None = None
    _cached_doc: object = None  # fitz.Document when open

    @classmethod
    def convert_page(cls, pdf_path: str, page_num: int, dpi: int = 300) -> object | None:
        """
        Converts a single page of a PDF to a PIL Image using fitz.
        page_num is 0-indexed.
        """
        try:
            if cls._cached_path != pdf_path:
                if cls._cached_doc is not None:
                    try:
                        cls._cached_doc.close()
                    except Exception:
                        pass
                cls._cached_doc = fitz.open(pdf_path)
                cls._cached_path = pdf_path

            if page_num < 0 or page_num >= len(cls._cached_doc):
                return None

            page = cls._cached_doc[page_num]

            # Standard PDF unit is 72 DPI.
            # To get 300 DPI, we need a scale of 300 / 72.
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Convert fitz pixmap to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            return img
        except Exception as e:
            print(f"Error converting PDF page with fitz: {e}")
            return None

    @classmethod
    def close_cache(cls) -> None:
        """Close and release the cached fitz document."""
        if cls._cached_doc is not None:
            try:
                cls._cached_doc.close()
            except Exception:
                pass
            cls._cached_doc = None
            cls._cached_path = None

    @classmethod
    def get_page_count(cls, pdf_path: str) -> int:
        """Returns the total number of pages in the PDF."""
        doc = None
        try:
            doc = fitz.open(pdf_path)
            count = len(doc)
            return count
        except (FileNotFoundError, PermissionError) as e:
            print(f"[converter.py] Cannot open PDF {pdf_path}: {e}")
            return 0
        except Exception as e:
            print(f"[converter.py] Unexpected error reading {pdf_path}: {e}")
            return 0
        finally:
            if doc:
                doc.close()
