"""Provider-neutral email contract. No provider, credentials or console fallback.

A deployment adapter must deliver via the approved provider before workflows are
connected. Links belong in email only, never API responses or diagnostics.
"""
from typing import Protocol
from fastapi import HTTPException

class AuthEmailDelivery(Protocol):
    def send(self, *, recipient: str, purpose: str, link: str) -> None: ...

class UnconfiguredAuthEmailDelivery:
    def send(self, *, recipient: str, purpose: str, link: str) -> None:
        raise HTTPException(503,'Authentication email delivery is not configured.')
