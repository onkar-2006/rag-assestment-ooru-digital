import os
from typing import Dict, List, Any
from backend.parser.pdf_parser import FastPDFParser
from backend.parser.docx_parser import FastDOCXParser

class UniversalDocumentParser:
    """
    Unified Production Document Parser.
    Automatically detects file extension (.pdf, .docx, .doc) and routes to optimal high-speed parser.
    Returns normalized parsed document representation.
    """
    def __init__(self):
        self.pdf_parser = FastPDFParser()
        self.docx_parser = FastDOCXParser()

    def parse(self, file_path: str) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found at: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            return self.pdf_parser.parse(file_path)
        elif ext in [".docx", ".doc"]:
            return self.docx_parser.parse(file_path)
        else:
            raise ValueError(f"Unsupported document format '{ext}'. Supported formats: .pdf, .docx")
