import time
import os
import re
from typing import Dict, List, Any, Optional
from collections import Counter
import fitz  # PyMuPDF

class FastPDFParser:
    """
    Production-Grade, Layout-Aware PDF Parser.
    Converts PDF documents into structural elements (Headings, Paragraphs, Lists, Tables, URLs).
    """
    def __init__(self, font_diff_threshold: float = 1.8):
        self.font_diff_threshold = font_diff_threshold

    def parse(self, pdf_path: str) -> Dict[str, Any]:
        """Parses a PDF document into a structured dict object."""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

        start_time = time.perf_counter()
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        doc_name = os.path.basename(pdf_path)

        most_common_size = self._profile_body_font_size(doc)

        parsed_pages = []
        for page_idx, page in enumerate(doc):
            page_num = page_idx + 1
            tables, table_bboxes = self._extract_tables(page)
            page_links = self._extract_hyperlinks(page)
            elements = self._extract_text_elements(page, most_common_size, table_bboxes, page_links)

            parsed_pages.append({
                "page": page_num,
                "elements": elements,
                "tables": tables
            })

        elapsed_time = time.perf_counter() - start_time

        return {
            "doc_name": doc_name,
            "total_pages": total_pages,
            "processing_time_seconds": round(elapsed_time, 4),
            "pages_per_second": round(total_pages / elapsed_time, 2) if elapsed_time > 0 else 0,
            "body_font_size": most_common_size,
            "pages": parsed_pages
        }

    def _profile_body_font_size(self, doc: fitz.Document) -> float:
        font_sizes = []
        for page in doc:
            blocks = page.get_text("dict", flags=fitz.TEXT_DEHYPHENATE).get("blocks", [])
            for b in blocks:
                if b.get("type") == 0:
                    for line in b.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            if text:
                                font_sizes.append(round(span.get("size", 0), 1))
        return Counter(font_sizes).most_common(1)[0][0] if font_sizes else 10.0

    def _extract_tables(self, page: fitz.Page) -> tuple[List[Dict[str, Any]], List[tuple]]:
        page_tables = []
        table_bboxes = []
        try:
            tabs = page.find_tables()
            for tab in tabs:
                extracted_grid = tab.extract()
                if extracted_grid and len(extracted_grid) >= 2:
                    clean_rows = []
                    for row in extracted_grid:
                        clean_row = []
                        for cell in row:
                            if cell is not None:
                                text_c = str(cell).replace("\n", " ").strip()
                                text_c = re.sub(r'(\w+)-\s+(\w+)', r'\1-\2', text_c)
                                clean_row.append(text_c)
                            else:
                                clean_row.append("")
                        if any(clean_row):
                            clean_rows.append(clean_row)
                    
                    if len(clean_rows) >= 2 and len(clean_rows[0]) >= 2:
                        max_cell_len = max(len(c) for r in clean_rows for c in r)
                        if max_cell_len < 250:
                            page_tables.append({
                                "bbox": tab.bbox,
                                "rows": clean_rows
                            })
                            table_bboxes.append(tab.bbox)
        except Exception:
            pass
        return page_tables, table_bboxes

    def _extract_hyperlinks(self, page: fitz.Page) -> List[Dict[str, Any]]:
        page_links = []
        try:
            links = page.get_links()
            for l in links:
                if l.get("kind") == fitz.LINK_URI and l.get("uri"):
                    page_links.append({"bbox": l.get("from"), "uri": l.get("uri")})
        except Exception:
            pass
        return page_links

    def _extract_text_elements(
        self, 
        page: fitz.Page, 
        most_common_size: float, 
        table_bboxes: List[tuple], 
        page_links: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        elements = []
        text_page = page.get_text("dict", flags=fitz.TEXT_DEHYPHENATE)
        
        for b in text_page.get("blocks", []):
            if b.get("type") == 0:
                block_bbox = b.get("bbox")
                if self._is_inside_table(block_bbox, table_bboxes):
                    continue

                block_text = ""
                max_font_size = 0
                is_bold = False

                for line in b.get("lines", []):
                    line_text = ""
                    for span in line.get("spans", []):
                        span_text = span.get("text", "")
                        line_text += span_text
                        size = round(span.get("size", 0), 1)
                        if size > max_font_size:
                            max_font_size = size
                        flags = span.get("flags", 0)
                        font_name = span.get("font", "").lower()
                        if (flags & 2 != 0) or ("bold" in font_name) or ("black" in font_name):
                            is_bold = True
                    
                    block_text += line_text.strip() + " "

                block_text = block_text.strip()
                if not block_text:
                    continue

                url = self._get_overlapping_url(block_bbox, page_links)
                if url and not block_text.startswith("["):
                    block_text = f"[{block_text}]({url})"

                if max_font_size > most_common_size + 4:
                    element_type = "H1_TITLE"
                elif max_font_size > most_common_size + 1.8 or (max_font_size >= most_common_size and is_bold and len(block_text) < 120):
                    element_type = "H2_HEADING"
                elif is_bold and len(block_text) < 80:
                    element_type = "H3_SUBHEADING"
                elif block_text.startswith(("•", "-", "*", "1.", "2.", "3.", "4.")):
                    element_type = "LIST_ITEM"
                else:
                    element_type = "PARAGRAPH"

                elements.append({
                    "type": element_type,
                    "text": block_text,
                    "font_size": max_font_size,
                    "is_bold": is_bold,
                    "url": url,
                    "bbox": block_bbox
                })

        return elements

    @staticmethod
    def _is_inside_table(block_bbox: tuple, t_bboxes: List[tuple]) -> bool:
        if not block_bbox or not t_bboxes:
            return False
        bx0, by0, bx1, by1 = block_bbox
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        for tx0, ty0, tx1, ty1 in t_bboxes:
            if (tx0 - 5 <= cx <= tx1 + 5) and (ty0 - 5 <= cy <= ty1 + 5):
                return True
        return False

    @staticmethod
    def _get_overlapping_url(block_bbox: tuple, links_list: List[Dict[str, Any]]) -> Optional[str]:
        if not block_bbox or not links_list:
            return None
        bx0, by0, bx1, by1 = block_bbox
        for link in links_list:
            lx0, ly0, lx1, ly1 = link["bbox"]
            if not (bx1 < lx0 or bx0 > lx1 or by1 < ly0 or by0 > ly1):
                return link["uri"]
        return None
