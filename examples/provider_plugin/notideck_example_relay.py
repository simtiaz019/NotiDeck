"""Example trusted external plugin: a real HTTP relay, not a fake sender."""

from notideck.providers.builtin import Builtin


class Relay:
    provider_type = "example_relay"

    def __init__(self):
        self.delegate = Builtin("webhook")

    def configuration_schema(self):
        return self.delegate.configuration_schema()

    def validate_configuration(self, config):
        return self.delegate.validate_configuration(config)

    def supported_capabilities(self):
        return self.delegate.supported_capabilities()

    def test_connection(self, config):
        return self.delegate.test_connection(config)

    def send(self, config, message, recipient=None):
        return self.delegate.send(config, message, recipient)
