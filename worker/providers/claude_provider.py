import json
import logging
from typing import Any, Dict

from anthropic import Anthropic

from worker.config import CLAUDE_API_KEY, CLAUDE_MODEL
from worker.providers.base import IAProvider, ProviderError

logger = logging.getLogger(__name__)


class ClaudeProvider(IAProvider):
    def __init__(self) -> None:
        self.api_key = CLAUDE_API_KEY
        self.model_name = CLAUDE_MODEL

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str) -> Dict[str, Any]:
        text = ""
        try:
            client = Anthropic(api_key=self.api_key)
            message = client.messages.create(
                model=self.model_name,
                max_tokens=1500,
                temperature=0.2,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                system="Responda somente JSON válido.",
            )
            text = message.content[0].text if message.content else "{}"
            return json.loads(_extract_json(text))
        except Exception as exc:
            if text:
                logger.error(
                    "Claude resposta bruta (primeiros 500 chars): %s", text[:500]
                )
            logger.exception("Claude falhou")
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
