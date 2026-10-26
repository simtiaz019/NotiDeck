"""Stable v1 provider protocol and locally trusted entry-point registry."""

from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Protocol


@dataclass
class Result:
    success: bool
    retryable: bool = False
    message_id: str | None = None
    code: str | None = None
    error: str | None = None
    retry_after: float | None = None
    accepted_at: float | None = None


class Provider(Protocol):
    provider_type: str

    def configuration_schema(self) -> dict: ...
    def validate_configuration(self, config: dict) -> dict: ...
    def supported_capabilities(self) -> list[str]: ...
    def send(self, config: dict, message: dict, recipient: str | None = None) -> Result: ...
    def test_connection(self, config: dict) -> Result: ...


def registry():
    from .builtin import Builtin

    providers = {name: Builtin(name) for name in Builtin.fields}
    for ep in entry_points(group="notideck.providers"):
        provider = ep.load()()
        if provider.provider_type in providers:
            raise RuntimeError("Provider name collision")
        providers[provider.provider_type] = provider
    return providers
