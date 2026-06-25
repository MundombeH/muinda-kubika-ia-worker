import os
from typing import Iterable

BLOCKED_EXTENSIONS = {
    "exe",
    "msi",
    "bat",
    "cmd",
    "sh",
    "apk",
    "jar",
    "war",
    "dll",
    "so",
    "iso",
    "class",
    "o",
    "a",
    "dylib",
    "lib",
    "pyc",
    "min.js",
    "map",
}

DEPENDENCY_DIRS = {
    "node_modules",
    "target",
    "build",
    "dist",
    "vendor",
    ".gradle",
    ".mvn",
    ".venv",
    "__pycache__",
    ".git",
}

ALLOWED_DOCS = {"pdf", "doc", "docx", "odt", "txt", "rtf"}
ALLOWED_PRESENTATIONS = {"ppt", "pptx", "odp"}
ALLOWED_SHEETS = {"xls", "xlsx", "ods", "csv"}
ALLOWED_IMAGES = {"png", "jpg", "jpeg", "webp", "gif", "tiff"}
ALLOWED_CODE = {
    "java",
    "py",
    "js",
    "ts",
    "go",
    "rb",
    "php",
    "cs",
    "cpp",
    "c",
    "kt",
    "swift",
    "rs",
    "sql",
    "md",
    "yaml",
    "yml",
    "json",
}


def get_extension(filename: str) -> str:
    if not filename:
        return ""
    base = os.path.basename(filename).lower()
    if "." not in base:
        return ""
    parts = base.split(".")
    if len(parts) >= 3 and parts[-2] == "min" and parts[-1] == "js":
        return "min.js"
    return parts[-1]


def is_blocked_extension(ext: str) -> bool:
    return ext in BLOCKED_EXTENSIONS


def is_allowed_extension(ext: str, allow_code: bool = True) -> bool:
    if ext in ALLOWED_DOCS | ALLOWED_PRESENTATIONS | ALLOWED_SHEETS | ALLOWED_IMAGES:
        return True
    if allow_code and ext in ALLOWED_CODE:
        return True
    return False


def has_dependency_dir(path_parts: Iterable[str]) -> bool:
    return any(part in DEPENDENCY_DIRS for part in path_parts)
