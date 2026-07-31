import math
from typing import List, Dict, Any, Optional

class SectionAwareChunker:
    """
    Production Section-Aware Hierarchy Chunker.
    Tracks heading breadcrumbs, preserves atomic Markdown tables, and attaches grounding metadata.
    """
    def __init__(self, target_max_tokens: int = 450, overlap_tokens: int = 40):
        self.target_max_tokens = target_max_tokens
        self.overlap_tokens = overlap_tokens

    @staticmethod
    def estimate_tokens(text: str) -> int:
        words = text.split()
        return math.ceil(len(words) * 1.3)

    @staticmethod
    def is_valid_heading(text: str) -> bool:
        if not text:
            return False
        clean_t = text.strip()
        if clean_t.startswith("arXiv:") or clean_t.isdigit():
            return False
        if len(clean_t) <= 3 and not clean_t.isalnum():
            return False
        return True

    def chunk_document(self, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        doc_name = parsed_data.get("doc_name", "Document")
        chunks = []
        chunk_counter = 1

        current_h1: Optional[str] = None
        current_h2: Optional[str] = None
        current_h3: Optional[str] = None

        def get_section_path() -> str:
            path_parts = [p for p in [current_h1, current_h2, current_h3] if p]
            return " > ".join(path_parts) if path_parts else doc_name

        accumulated_elements = []
        accumulated_pages = set()
        current_tokens = 0

        def flush_text_chunk():
            nonlocal chunk_counter, accumulated_elements, accumulated_pages, current_tokens
            if not accumulated_elements:
                return

            section_path = get_section_path()
            body_text = "\n\n".join([e["text"] for e in accumulated_elements])
            context_header = f"[Context: {section_path}]"
            full_content = f"{context_header}\n{body_text}"
            token_count = self.estimate_tokens(full_content)
            page_list = sorted(list(accumulated_pages))

            chunks.append({
                "chunk_id": f"chunk_{chunk_counter:04d}",
                "doc_name": doc_name,
                "page_numbers": page_list,
                "section_path": section_path,
                "chunk_type": "TEXT_SECTION",
                "token_count": token_count,
                "content": full_content,
                "raw_text": body_text
            })
            chunk_counter += 1

            if self.overlap_tokens > 0 and len(accumulated_elements) > 1:
                last_elem = accumulated_elements[-1]
                accumulated_elements = [last_elem]
                accumulated_pages = {last_elem.get("page", page_list[-1])}
                current_tokens = self.estimate_tokens(last_elem["text"])
            else:
                accumulated_elements = []
                accumulated_pages = set()
                current_tokens = 0

        for page_data in parsed_data.get("pages", []):
            page_num = page_data["page"]
            elements = page_data.get("elements", [])
            tables = page_data.get("tables", [])

            for elem in elements:
                e_type = elem["type"]
                text = elem["text"]
                elem["page"] = page_num

                if e_type == "H1_TITLE" and self.is_valid_heading(text):
                    flush_text_chunk()
                    current_h1 = text
                    current_h2 = None
                    current_h3 = None
                    continue
                elif e_type == "H2_HEADING" and self.is_valid_heading(text):
                    flush_text_chunk()
                    current_h2 = text
                    current_h3 = None
                    continue
                elif e_type == "H3_SUBHEADING" and self.is_valid_heading(text):
                    flush_text_chunk()
                    current_h3 = text
                    continue

                elem_tokens = self.estimate_tokens(text)
                if current_tokens + elem_tokens > self.target_max_tokens and accumulated_elements:
                    flush_text_chunk()

                accumulated_elements.append(elem)
                accumulated_pages.add(page_num)
                current_tokens += elem_tokens

            for tab_idx, tab in enumerate(tables):
                flush_text_chunk()
                rows = tab.get("rows", [])
                if not rows:
                    continue

                header = "| " + " | ".join(rows[0]) + " |"
                divider = "| " + " | ".join(["---"] * len(rows[0])) + " |"
                data_rows = ["| " + " | ".join(row) + " |" for row in rows[1:]]
                table_md = "\n".join([header, divider] + data_rows)

                section_path = get_section_path()
                context_header = f"[Context: {section_path} > Table {tab_idx + 1}]"
                full_content = f"{context_header}\n{table_md}"
                token_count = self.estimate_tokens(full_content)

                chunks.append({
                    "chunk_id": f"chunk_{chunk_counter:04d}",
                    "doc_name": doc_name,
                    "page_numbers": [page_num],
                    "section_path": f"{section_path} > Table {tab_idx + 1}",
                    "chunk_type": "ATOMIC_TABLE",
                    "token_count": token_count,
                    "content": full_content,
                    "table_structure": {
                        "headers": rows[0],
                        "num_rows": len(rows),
                        "num_cols": len(rows[0])
                    }
                })
                chunk_counter += 1

        flush_text_chunk()
        return chunks
