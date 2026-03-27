import os
import fitz
from PIL import Image
import io

class PDFToImageConverter:
    """
    Handles converting PDF pages to high-resolution images for precision cropping.
    Uses PyMuPDF (fitz) to avoid Poppler dependency.
    """
    @staticmethod
    def convert_page(pdf_path, page_num, dpi=300):
        """
        Converts a single page of a PDF to a PIL Image using fitz.
        page_num is 0-indexed.
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            if page_num < 0 or page_num >= len(doc):
                return None
            
            page = doc[page_num]
            
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
        finally:
            if doc:
                doc.close()


    @staticmethod
    def get_page_count(pdf_path):
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
