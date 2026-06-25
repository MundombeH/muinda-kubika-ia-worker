import json
import logging
from typing import Any, Dict

import google.generativeai as genai

from worker.config import GEMINI_API_KEY, GEMINI_MODEL
from worker.providers.base import IAProvider, ProviderError

logger = logging.getLogger(__name__)


def _normalize_model_name(model_name: str) -> str:
    normalized = (model_name or "").strip()
    if normalized.startswith("models/"):
        normalized = normalized.split("/", 1)[1]
    return normalized


class GeminiProvider(IAProvider):
    def __init__(self) -> None:
        self.api_key = GEMINI_API_KEY
        self.model_name = _normalize_model_name(GEMINI_MODEL)

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str) -> Dict[str, Any]:
        text = ""
        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(prompt)
            text = response.text or ""
            return json.loads(_extract_json(text))
        except Exception as exc:
            if text:
                logger.error(
                    "Gemini resposta bruta (primeiros 500 chars): %s", text[:500]
                )
            logger.exception("Gemini falhou")
            raise ProviderError(str(exc))


def _extract_json(text: str) -> str:
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            start = part.find("{")
            end = part.rfind("}")
            if start != -1 and end != -1 and end >= start:
                return part[start : end + 1]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end >= start:
        return text[start : end + 1]
    return "{}"
