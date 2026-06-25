import logging
from typing import Dict, Any, List

from worker.providers.base import IAProvider, ProviderError

logger = logging.getLogger(__name__)


class FallbackProvider:
    def __init__(self, providers: List[IAProvider]) -> None:
        self.providers = providers

    def generate(self, prompt: str) -> Dict[str, Any]:
        last_error = None
        for provider in self.providers:
            if not provider.is_configured():
                logger.info("Provider %s não configurado, pulando", provider.__class__.__name__)
                continue
            try:
                logger.info("Usando provider: %s", provider.__class__.__name__)
                return provider.generate(prompt)
            except ProviderError as exc:
                last_error = exc
                logger.warning("Provider falhou: %s", exc)
                continue

        raise ProviderError(str(last_error) if last_error else "Nenhum provider configurado")
