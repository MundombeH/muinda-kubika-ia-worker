import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List

from worker.config import GIT_CLONE_DEPTH
from worker.utils.file_utils import (
    get_extension,
    has_dependency_dir,
    is_allowed_extension,
    is_blocked_extension,
)
from worker.utils.limits import Limits

logger = logging.getLogger(__name__)

PRIORITY_FILENAMES = {
    "readme.md": 0,
    "readme.txt": 1,
    "readme": 2,
    "package.json": 3,
    "package-lock.json": 4,
    "pom.xml": 5,
    "build.gradle": 6,
    "build.gradle.kts": 7,
    "settings.gradle": 8,
    "settings.gradle.kts": 9,
    "requirements.txt": 10,
    "pyproject.toml": 11,
    "poetry.lock": 12,
    "pipfile": 13,
    "pipfile.lock": 14,
    "dockerfile": 15,
    "docker-compose.yml": 16,
    "docker-compose.yaml": 17,
    "compose.yml": 18,
    "compose.yaml": 19,
    ".env.example": 20,
    "go.mod": 21,
    "go.sum": 22,
    "cargo.toml": 23,
    "cargo.lock": 24,
    "composer.json": 25,
    "composer.lock": 26,
    "gemfile": 27,
    "gemfile.lock": 28,
    "tsconfig.json": 29,
    "vite.config.ts": 30,
    "vite.config.js": 31,
    "next.config.js": 32,
    "next.config.mjs": 33,
    "angular.json": 34,
    "pubspec.yaml": 35,
    "pubspec.lock": 36,
}

PRIORITY_SUFFIXES = (
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
)


GIT_CLONE_TIMEOUT = 300


def clone_repo(repo_url: str) -> Path:
    temp_dir = Path(tempfile.mkdtemp())
    dest = temp_dir / "repo"
    subprocess.run(
        ["git", "clone", "--depth", str(GIT_CLONE_DEPTH), repo_url, str(dest)],
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_CLONE_TIMEOUT,
    )
    return dest


def _priority_key(repo_path: Path, path: Path) -> tuple[int, int, str]:
    rel_path = path.relative_to(repo_path)
    rel_str = rel_path.as_posix().lower()
    filename = path.name.lower()

    if filename in PRIORITY_FILENAMES:
        return (0, PRIORITY_FILENAMES[filename], rel_str)
    if filename.startswith("readme"):
        return (0, 100, rel_str)
    if rel_path.parent == Path(".") and filename.endswith(PRIORITY_SUFFIXES):
        return (1, 0, rel_str)
    if rel_path.parent == Path("."):
        return (2, 0, rel_str)
    if filename.endswith(PRIORITY_SUFFIXES):
        return (3, 0, rel_str)
    return (4, 0, rel_str)


def collect_repo_files(repo_path: Path, limits: Limits) -> List[Path]:
    candidates: List[Path] = []

    for path in repo_path.rglob("*"):
        if path.is_dir():
            continue
        rel_parts = path.relative_to(repo_path).parts
        if has_dependency_dir(rel_parts):
            continue
        ext = get_extension(path.name)
        if is_blocked_extension(ext) or not is_allowed_extension(ext, allow_code=True):
            continue
        candidates.append(path)

    candidates.sort(key=lambda path: _priority_key(repo_path, path))

    collected: List[Path] = []
    total_size = 0
    for path in candidates:
        size = path.stat().st_size
        if total_size + size > limits.max_total_bytes:
            continue
        total_size += size
        collected.append(path)
        if len(collected) >= limits.max_zip_files:
            break

    logger.info("Ficheiros coletados no repo: %s", len(collected))
    if collected:
        logger.info(
            "Ficheiros priorizados no repo: %s",
            [str(path.relative_to(repo_path)) for path in collected[:10]],
        )
    return collected


def cleanup_repo(repo_path: Path) -> None:
    shutil.rmtree(repo_path.parent, ignore_errors=True)
