from abc import ABC, abstractmethod
from typing import Dict, Any


class ProviderError(Exception):
    pass


class IAProvider(ABC):
    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def generate(self, prompt: str) -> Dict[str, Any]:
        raise NotImplementedError
