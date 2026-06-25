import logging
import os
import tempfile
from pathlib import Path
from typing import List

import requests

from worker.processors.text_extractors import extract_text
from worker.utils.file_utils import (
    get_extension,
    is_allowed_extension,
    is_blocked_extension,
)
from worker.utils.limits import Limits

logger = logging.getLogger(__name__)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def download_file(url: str, max_total_bytes: int, source_name: str = "") -> Path:
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    total = 0
    ext = get_extension(source_name or url)
    suffix = f".{ext}" if ext else ""
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    path = Path(temp_path)

    with path.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_total_bytes:
                raise ValueError("Arquivo excede o limite total permitido")
            handle.write(chunk)
    return path


def process_single_file(path: Path, limits: Limits) -> str:
    ext = path.suffix.lower().lstrip(".")

    if is_blocked_extension(ext):
        logger.info("Extensão bloqueada: %s", ext)
        return ""

    if not is_allowed_extension(ext, allow_code=True):
        logger.info("Extensão não permitida: %s", ext)
        return ""

    size = path.stat().st_size
    if ext == "pdf" and size > limits.max_pdf_bytes:
        raise ValueError("PDF excede o tamanho máximo")
    if ext in {"docx", "doc"} and size > limits.max_docx_bytes:
        raise ValueError("DOC/DOCX excede o tamanho máximo")
    if (
        ext in {"png", "jpg", "jpeg", "webp", "gif", "tiff"}
        and size > limits.max_image_bytes
    ):
        raise ValueError("Imagem excede o tamanho máximo")

    return extract_text(path)


def build_text_from_paths(paths: List[Path], limits: Limits) -> str:
    chunks = []
    total_chars = 0
    for path in paths:
        text = process_single_file(path, limits)
        if not text:
            continue
        text = _truncate(text, limits.max_text_chars)
        total_chars += len(text)
        if total_chars > limits.max_text_chars:
            break
        chunks.append(f"\n\n### {path.name}\n{text}")

    return _truncate("".join(chunks), limits.max_text_chars)
