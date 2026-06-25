import os

from dotenv import load_dotenv

load_dotenv()


def _get_required(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Variável de ambiente obrigatória ausente ou vazia: {name}")
    return value.strip()


def _get_optional(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Variável {name} deve ser um inteiro. Valor recebido: {raw!r}"
        ) from exc


# Obrigatórias para funcionamento do worker em produção
RABBITMQ_URL = _get_required("RABBITMQ_URL")
API_BASE_URL = _get_required("API_BASE_URL").rstrip("/")
IA_WORKER_TOKEN = _get_required("IA_WORKER_TOKEN")

# Opcional (mantém default seguro para fila)
RABBITMQ_QUEUE = _get_optional("RABBITMQ_QUEUE", "documento.ia.queue")

# Chaves de providers são opcionais (fallback entre provedores)
GEMINI_API_KEY = _get_optional("GEMINI_API_KEY")
GEMINI_MODEL = _get_optional("GEMINI_MODEL", "gemini-1.5-flash")

GROQ_API_KEY = _get_optional("GROQ_API_KEY")
GROQ_MODEL = _get_optional("GROQ_MODEL", "llama3-70b-8192")

OPENAI_API_KEY = _get_optional("OPENAI_API_KEY")
OPENAI_MODEL = _get_optional("OPENAI_MODEL", "gpt-4o-mini")

CLAUDE_API_KEY = _get_optional("CLAUDE_API_KEY")
CLAUDE_MODEL = _get_optional("CLAUDE_MODEL", "claude-3-5-sonnet-20240620")

MAX_TOTAL_MB = _get_int("MAX_TOTAL_MB", 100)
MAX_ZIP_FILES = _get_int("MAX_ZIP_FILES", 50)
MAX_TEXT_CHARS = _get_int("MAX_TEXT_CHARS", 120000)

MAX_PDF_MB = _get_int("MAX_PDF_MB", 50)
MAX_DOCX_MB = _get_int("MAX_DOCX_MB", 20)
MAX_IMAGE_MB = _get_int("MAX_IMAGE_MB", 10)

GIT_CLONE_DEPTH = _get_int("GIT_CLONE_DEPTH", 1)
