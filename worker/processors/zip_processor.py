import logging
import tempfile
from pathlib import Path
from typing import List
from zipfile import ZipFile

from worker.utils.file_utils import get_extension, is_allowed_extension, is_blocked_extension, has_dependency_dir
from worker.utils.limits import Limits

logger = logging.getLogger(__name__)


def extract_zip(zip_path: Path, limits: Limits) -> List[Path]:
    extracted_paths: List[Path] = []
    total_size = 0

    with ZipFile(zip_path) as zip_file:
        members = [m for m in zip_file.infolist() if not m.is_dir()]
        if len(members) > limits.max_zip_files:
            raise ValueError("ZIP excede o número máximo de ficheiros")

        temp_dir = Path(tempfile.mkdtemp())

        for info in members:
            parts = Path(info.filename).parts
            if has_dependency_dir(parts):
                continue

            ext = get_extension(info.filename)
            if is_blocked_extension(ext) or not is_allowed_extension(ext, allow_code=True):
                continue

            total_size += info.file_size
            if total_size > limits.max_total_bytes:
                raise ValueError("ZIP excede o tamanho total máximo")

            extracted_path = Path(zip_file.extract(info, path=temp_dir))
            extracted_paths.append(extracted_path)

    logger.info("ZIP extraído: %s ficheiros", len(extracted_paths))
    return extracted_paths
