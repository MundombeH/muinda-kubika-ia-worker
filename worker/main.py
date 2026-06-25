import json
import logging
import os
from pathlib import Path

import pika
import requests

from worker import config
from worker.processors.file_processor import build_text_from_paths, download_file
from worker.processors.repo_processor import (
    cleanup_repo,
    clone_repo,
    collect_repo_files,
)
from worker.processors.zip_processor import extract_zip
from worker.providers.base import ProviderError
from worker.providers.claude_provider import ClaudeProvider
from worker.providers.fallback import FallbackProvider
from worker.providers.gemini_provider import GeminiProvider
from worker.providers.groq_provider import GroqProvider
from worker.providers.openai_provider import OpenAIProvider
from worker.utils.file_utils import get_extension
from worker.utils.limits import Limits

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def build_prompt(text: str, metadata: dict) -> str:
    tipo_documento = metadata.get("tipoDocumento") or ""
    file_name = _resolve_source_name(metadata)
    origem_analise = metadata.get("origemAnalise") or (
        "REPOSITORIO"
        if is_github_repo(str(metadata.get("fileUrl") or ""))
        else "FICHEIRO"
    )

    regras_especificas = """
Regras específicas para todas as análises:
- Responda em português.
- tagsSugeridas, categoriaSugerida e subcategoriaSugerida devem ficar em português.
- Baseie-se apenas em evidências presentes no conteúdo fornecido.
- Não invente autores, tecnologias ou frameworks.
"""

    if origem_analise == "REPOSITORIO":
        regras_especificas += """
Regras específicas para análise de REPOSITÓRIO:
- Trate o conteúdo como um repositório de código, não como um artigo científico.
- O título deve refletir o nome ou objetivo do projeto, não o nome da plataforma GitHub.
- O resumo deve descrever o propósito do projeto, a stack e os componentes principais observados no repositório.
- Preencha autores apenas se houver evidência textual forte no README, licença, metadados do projeto ou ficheiros analisados. Caso contrário, devolva lista vazia.
- Em tecnologiasSugeridas, inclua apenas linguagens, ferramentas, bibliotecas, runtimes ou serviços claramente evidenciados no código, dependências ou configurações.
- Não inclua tecnologias genéricas ou periféricas sem evidência forte, como SSH, HTTPS, internet ou GitHub, a menos que sejam parte central e explícita do projeto.
- Em frameworksSugeridos, inclua apenas frameworks efetivamente identificáveis no projeto. Se não houver evidência clara, devolva lista vazia.
- Dê preferência a evidências de README, ficheiros de build/dependências e configurações do projeto.
- Se o repositório for de exemplo, tutorial, demo ou estudo, isso deve aparecer no resumo e nas tags sugeridas.
"""

    return f"""
Analise o conteúdo abaixo. Tipo de documento: {tipo_documento}. Nome da origem analisada: {file_name}. Origem da análise: {origem_analise}.

Responda APENAS um JSON válido (sem markdown, sem explicações) com esta estrutura EXATA:
{{
  "titulo": "",
  "tituloConfianca": 0,
  "resumo": "",
  "autores": [""],
  "categoriaSugerida": "",
  "categoriaConfianca": 0,
  "subcategoriaSugerida": "",
  "subcategoriaConfianca": 0,
  "palavrasChaveIA": [{{"valor": "", "confianca": 0}}],
  "tagsSugeridas": [{{"valor": "", "confianca": 0}}],
  "tecnologiasSugeridas": [{{"valor": "", "confianca": 0}}],
  "frameworksSugeridos": [{{"valor": "", "confianca": 0}}],
  "conflitosDetectados": [""]
}}

Regras obrigatórias:
- Todos os campos de confiança (tituloConfianca, categoriaConfianca, subcategoriaConfianca e confianca das listas) devem ser inteiros de 0 a 100.
- Não use escala 0 a 1.
- Evite 100 quando houver incerteza; use 100 apenas quando a evidência no texto for muito forte.
- Se não houver evidência suficiente, use valores baixos (20-60) e deixe listas vazias quando necessário.
- Máximo de 15 itens por lista.
{regras_especificas}

Conteúdo:
{text}
"""


def is_github_repo(url: str) -> bool:
    return url.startswith("https://github.com/") or url.startswith("http://github.com/")


def _clean_text(value, max_len: int | None = None) -> str:
    if value is None:
        return ""
    cleaned = str(value).strip()
    if max_len is not None and len(cleaned) > max_len:
        return cleaned[:max_len].strip()
    return cleaned


def _normalize_confidence(value) -> int:
    try:
        if value is None:
            return 0
        numeric = float(value)
        if 0.0 <= numeric <= 1.0:
            numeric *= 100.0
        normalized = int(round(numeric))
    except Exception:
        return 0

    if normalized < 0:
        return 0
    if normalized > 100:
        return 100
    return normalized


def _normalize_unique_str_list(items, max_items: int = 15, item_max_len: int = 255):
    if not isinstance(items, list):
        return []

    normalized = []
    seen = set()
    for item in items:
        cleaned = _clean_text(item, item_max_len)
        if not cleaned:
            continue

        key = cleaned.lower()
        if key in seen:
            continue

        seen.add(key)
        normalized.append(cleaned)

        if len(normalized) >= max_items:
            break

    return normalized


def _normalize_sugestoes(items, max_items: int = 15):
    if not isinstance(items, list):
        return []

    normalized = []
    seen = set()

    for item in items:
        if not isinstance(item, dict):
            continue

        valor = _clean_text(item.get("valor"), 255)
        if not valor:
            continue

        key = valor.lower()
        if key in seen:
            continue

        seen.add(key)
        confianca = _normalize_confidence(item.get("confianca"))
        normalized.append({"valor": valor, "confianca": confianca})

        if len(normalized) >= max_items:
            break

    return normalized


def normalize_result(raw_result: dict) -> dict:
    result = raw_result if isinstance(raw_result, dict) else {}

    normalized = {
        "titulo": _clean_text(result.get("titulo"), 255),
        "tituloConfianca": _normalize_confidence(result.get("tituloConfianca")),
        "resumo": _clean_text(result.get("resumo"), 5000),
        "autores": _normalize_unique_str_list(result.get("autores"), max_items=15),
        "categoriaSugerida": _clean_text(result.get("categoriaSugerida"), 255),
        "categoriaConfianca": _normalize_confidence(result.get("categoriaConfianca")),
        "subcategoriaSugerida": _clean_text(result.get("subcategoriaSugerida"), 255),
        "subcategoriaConfianca": _normalize_confidence(
            result.get("subcategoriaConfianca")
        ),
        "palavrasChaveIA": _normalize_sugestoes(result.get("palavrasChaveIA", [])),
        "tagsSugeridas": _normalize_sugestoes(result.get("tagsSugeridas", [])),
        "tecnologiasSugeridas": _normalize_sugestoes(
            result.get("tecnologiasSugeridas", [])
        ),
        "frameworksSugeridos": _normalize_sugestoes(
            result.get("frameworksSugeridos", [])
        ),
        "conflitosDetectados": _normalize_unique_str_list(
            result.get("conflitosDetectados"), max_items=20, item_max_len=500
        ),
    }

    return normalized


def _normalize_extension(value: str | None) -> str:
    if not value:
        return ""
    normalized = str(value).strip().lower().lstrip(".")
    if "/" in normalized:
        normalized = normalized.split("/", 1)[1]
    return normalized


def _resolve_source_name(message: dict) -> str:
    file_name = (message.get("fileName") or "").strip()
    if file_name:
        return file_name

    file_url = (message.get("fileUrl") or "").strip()
    url_name = Path(file_url).name if file_url else ""
    if url_name and "." in url_name:
        return url_name

    ext = _normalize_extension(message.get("formato") or message.get("mimeType"))
    if ext:
        documento_id = message.get("documentoId") or "documento"
        return f"{documento_id}.{ext}"

    return url_name or "documento"


def process_message(message: dict) -> dict:
    limits = Limits(
        max_total_bytes=config.MAX_TOTAL_MB * 1024 * 1024,
        max_zip_files=config.MAX_ZIP_FILES,
        max_text_chars=config.MAX_TEXT_CHARS,
        max_pdf_bytes=config.MAX_PDF_MB * 1024 * 1024,
        max_docx_bytes=config.MAX_DOCX_MB * 1024 * 1024,
        max_image_bytes=config.MAX_IMAGE_MB * 1024 * 1024,
    )

    file_url = message.get("fileUrl")
    file_name = _resolve_source_name(message)
    logger.info("Nome de ficheiro resolvido para processamento: %s", file_name)

    if not file_url:
        raise ValueError("Mensagem sem fileUrl")

    if is_github_repo(file_url):
        repo_path = clone_repo(file_url)
        try:
            paths = collect_repo_files(repo_path, limits)
            text = build_text_from_paths(paths, limits)
        finally:
            cleanup_repo(repo_path)
    else:
        downloaded = download_file(file_url, limits.max_total_bytes, file_name)
        try:
            ext = get_extension(file_name or file_url)
            if ext == "zip":
                paths = extract_zip(downloaded, limits)
                text = build_text_from_paths(paths, limits)
            else:
                text = build_text_from_paths([downloaded], limits)
        finally:
            try:
                os.remove(downloaded)
            except OSError:
                pass

    prompt = build_prompt(text, message)

    provider = FallbackProvider(
        [GeminiProvider(), GroqProvider(), OpenAIProvider(), ClaudeProvider()]
    )

    result = provider.generate(prompt)
    result = normalize_result(result)

    documento_id = message.get("documentoId")
    if not documento_id:
        raise ValueError("Mensagem sem documentoId")

    origem_analise = message.get("origemAnalise")
    if not origem_analise:
        origem_analise = "REPOSITORIO" if is_github_repo(file_url) else "FICHEIRO"

    result["documentoId"] = documento_id
    result["origemAnalise"] = origem_analise
    return result


def send_result_to_api(result: dict) -> None:
    url = f"{config.API_BASE_URL}/ia/resultado"
    headers = {
        "Content-Type": "application/json",
        "X-IA-Worker-Token": config.IA_WORKER_TOKEN,
    }
    response = requests.post(url, headers=headers, data=json.dumps(result), timeout=60)
    response.raise_for_status()


def on_message(ch, method, properties, body) -> None:
    try:
        message = json.loads(body)
        logger.info("Mensagem recebida: %s", message.get("documentoId"))
        logger.info(
            "Payload completo: %s", json.dumps(message, ensure_ascii=False, default=str)
        )
    except Exception as exc:
        logger.exception("Mensagem inválida, descartando: %s", exc)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    try:
        result = process_message(message)
        logger.info(
            "Resultado gerado pela IA: %s",
            json.dumps(result, ensure_ascii=False, default=str),
        )
    except (ProviderError, ValueError, RuntimeError) as exc:
        logger.exception(
            "Falha ao gerar resultado da IA, descartando mensagem: %s", exc
        )
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return
    except Exception as exc:
        logger.exception("Falha inesperada ao processar mensagem, descartando: %s", exc)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    try:
        send_result_to_api(result)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except requests.RequestException as exc:
        logger.exception(
            "Falha ao enviar resultado para a API, recolocando na fila: %s", exc
        )
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    except Exception as exc:
        logger.exception(
            "Falha inesperada ao enviar resultado para a API, descartando: %s", exc
        )
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main() -> None:
    params = pika.URLParameters(config.RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=config.RABBITMQ_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=config.RABBITMQ_QUEUE, on_message_callback=on_message)

    logger.info("Worker iniciado. Aguardando mensagens...")
    channel.start_consuming()


if __name__ == "__main__":
    main()
