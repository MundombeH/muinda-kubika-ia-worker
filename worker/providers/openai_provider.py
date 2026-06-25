import json
import logging
from typing import Any, Dict

from openai import OpenAI

from worker.config import OPENAI_API_KEY, OPENAI_MODEL
from worker.providers.base import IAProvider, ProviderError

logger = logging.getLogger(__name__)


class OpenAIProvider(IAProvider):
    def __init__(self) -> None:
        self.api_key = OPENAI_API_KEY
        self.model_name = OPENAI_MODEL

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str) -> Dict[str, Any]:
        text = ""
        try:
            client = OpenAI(api_key=self.api_key)
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
                    "OpenAI resposta bruta (primeiros 500 chars): %s", text[:500]
                )
            logger.exception("OpenAI falhou")
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
