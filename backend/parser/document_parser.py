import os
from typing import Dict, List, Any
from backend.parser.pdf_parser import FastPDFParser
from backend.parser.docx_parser import FastDOCXParser
from backend.parser.ocr_parser import ImageOCRParser

class UniversalDocumentParser:
    """
    Unified Production Document Parser.
    Automatically detects file extension (.pdf, .docx, .png, .jpg, .jpeg, .tiff, .bmp)
    and routes to optimal high-speed parser. Returns normalized document representation.
    """
    def __init__(self):
        self.pdf_parser = FastPDFParser()
        self.docx_parser = FastDOCXParser()
        self.ocr_parser = ImageOCRParser()

    def parse(self, file_path: str) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found at: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            return self.pdf_parser.parse(file_path)
        elif ext in [".docx", ".doc"]:
            return self.docx_parser.parse(file_path)
        elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
            return self.ocr_parser.parse(file_path)
        else:
            raise ValueError(f"Unsupported document format '{ext}'. Supported formats: .pdf, .docx, .png, .jpg, .jpeg, .tiff, .bmp")

