import json
import logging
from typing import Any, Dict

from groq import Groq

from worker.config import GROQ_API_KEY, GROQ_MODEL
from worker.providers.base import IAProvider, ProviderError

logger = logging.getLogger(__name__)


class GroqProvider(IAProvider):
    def __init__(self) -> None:
        self.api_key = GROQ_API_KEY
        self.model_name = GROQ_MODEL

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str) -> Dict[str, Any]:
        text = ""
        try:
            client = Groq(api_key=self.api_key)
            completion = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Responda somente JSON válido."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            text = completion.choices[0].message.content or "{}"
            return json.loads(_extract_json(text))
        except Exception as exc:
            if text:
                logger.error(
                    "Groq resposta bruta (primeiros 500 chars): %s", text[:500]
                )
            logger.exception("Groq falhou")
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
