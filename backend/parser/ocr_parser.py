import os
from typing import Dict, List, Any
from PIL import Image

class ImageOCRParser:
    """
    High-Speed Image OCR Parser (Pillow + pytesseract).
    Parses standalone image formats (.png, .jpg, .jpeg, .tiff, .bmp),
    extracts layout-aware text, and formats into normalized document structure.
    """
    def __init__(self, tesseract_cmd: str = None):
        import pytesseract
        self.pytesseract = pytesseract
        
        # Windows Tesseract Executable auto-detection fallback
        if tesseract_cmd and os.path.exists(tesseract_cmd):
            self.pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        else:
            default_win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(default_win_path):
                self.pytesseract.pytesseract.tesseract_cmd = default_win_path

    def parse(self, file_path: str) -> Dict[str, Any]:
        """Parses image file and returns normalized layout JSON."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Image file not found at: {file_path}")

        file_name = os.path.basename(file_path)

        try:
            # 1. Open image via PIL & preprocess for optimal OCR contrast
            img = Image.open(file_path)
            if img.mode not in ("L", "RGB"):
                img = img.convert("RGB")

            # 2. Execute Tesseract OCR text extraction
            raw_text = self.pytesseract.image_to_string(img).strip()

            # 3. Fallback text if image contains no readable characters
            if not raw_text:
                raw_text = "[IMAGE OCR NOTICE: No legible text could be extracted from this image.]"

            # 4. Split extracted text into logical paragraph blocks
            lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

            # 5. Format into normalized pages and elements structure for SectionAwareChunker
            elements = []
            elements.append({"type": "H1_TITLE", "text": f"OCR Extracted Content ({file_name})"})
            for paragraph in lines:
                elements.append({"type": "PARAGRAPH", "text": paragraph})

            return {
                "doc_name": file_name,
                "total_pages": 1,
                "pages": [
                    {
                        "page": 1,
                        "elements": elements,
                        "tables": []
                    }
                ],
                "sections": [
                    {
                        "heading": f"OCR Extracted Content ({file_name})",
                        "level": 1,
                        "paragraphs": lines if lines else [raw_text],
                        "tables": [],
                        "hyperlinks": [],
                        "page_numbers": [1]
                    }
                ]
            }
        except Exception as err:
            print(f"[OCR ERROR] Failed to parse image {file_name}: {err}")

            return {
                "doc_name": file_name,
                "total_pages": 1,
                "pages": [
                    {
                        "page": 1,
                        "elements": [{"type": "H1_TITLE", "text": f"OCR Error ({file_name})"}, {"type": "PARAGRAPH", "text": f"Error extracting text: {err}"}],
                        "tables": []
                    }
                ],
                "sections": [
                    {
                        "heading": f"OCR Extraction Error ({file_name})",
                        "level": 1,
                        "paragraphs": [f"Error extracting text from image: {err}"],
                        "tables": [],
                        "hyperlinks": [],
                        "page_numbers": [1]
                    }
                ]
            }


