"""Provider boundary for photography suggestions; no external provider is configured in Part 1."""

from typing import Protocol

from app.schemas.photography_suggestions import PhotographySuggestions


class SuggestionsProviderUnavailable(RuntimeError):
    """Raised when no suggestions provider has been configured."""


class SuggestionsProvider(Protocol):
    async def generate(self, prompt: str) -> PhotographySuggestions:
        """Return suggestions matching the strict response contract."""


class UnconfiguredSuggestionsProvider:
    async def generate(self, prompt: str) -> PhotographySuggestions:
        raise SuggestionsProviderUnavailable("Photography suggestions provider is not configured.")


suggestions_provider = UnconfiguredSuggestionsProvider()


def get_suggestions_provider() -> SuggestionsProvider:
    return suggestions_provider
