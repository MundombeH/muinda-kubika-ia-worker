import logging
from pathlib import Path
from tika import parser

from worker.utils.file_utils import ALLOWED_CODE, ALLOWED_IMAGES

logger = logging.getLogger(__name__)


def extract_text(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")

    if ext in ALLOWED_CODE or ext in {"txt", "md", "json", "yaml", "yml", "csv", "sql"}:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logger.warning("Falha ao ler texto direto: %s", exc)

    if ext in ALLOWED_IMAGES:
        return ""

    try:
        parsed = parser.from_file(str(path))
        return (parsed.get("content") or "").strip()
    except Exception as exc:
        logger.warning("Falha ao extrair texto com Tika: %s", exc)
        return ""
