from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    max_total_bytes: int
    max_zip_files: int
    max_text_chars: int
    max_pdf_bytes: int
    max_docx_bytes: int
    max_image_bytes: int
