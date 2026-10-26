import json
from unittest.mock import MagicMock

import httpx
import pytest

from notideck.providers.builtin import Builtin
from notideck.security import SafeNetwork

MESSAGE = {"id": "n1", "title": "Alert", "message": "Details", "severity": "ERROR"}
CONFIGS = {
    "telegram": {"bot_token": "token", "chat_id": "123"},
    "slack": {"webhook_url": "https://hooks.slack.com/services/secret"},
    "discord": {"webhook_url": "https://discord.com/api/webhooks/secret"},
    "webhook": {"url": "https://example.com", "hmac_secret": "secret"},
    "whatsapp": {
        "access_token": "secret",
        "phone_number_id": "123",
        "recipient": "15555550100",
        "api_version": "v23.0",
        "template_name": "alert",
        "language": "en_US",
    },
    "sms": {
        "account_sid": "AC123",
        "auth_token": "secret",
        "from_number": "+15555550100",
        "to": "+15555550101",
    },
    "signal": {"url": "http://signal.example.com", "account": "+15555550100", "recipient": "+15555550101"},
}


@pytest.mark.parametrize("provider", list(CONFIGS))
def test_provider_requests(provider, monkeypatch):
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "ok": True,
                "timestamp": 123456789,
                "result": {"message_id": 123},
                "sid": "SM123",
                "messages": [{"id": "wamid1"}],
            },
        )

    monkeypatch.setattr(
        "notideck.providers.builtin.safe_http",
        lambda timeout: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = Builtin(provider).send(CONFIGS[provider], MESSAGE)
    assert result.success
    request = captured[0]
    assert request.method == "POST"
    if provider == "sms":
        assert b"To=%2B15555550101" in request.content
        assert request.headers["Authorization"].startswith("Basic ")
    if provider == "telegram":
        assert json.loads(request.content)["chat_id"] == "123"
    if provider == "whatsapp":
        assert json.loads(request.content)["template"]["name"] == "alert"
    if provider == "webhook":
        assert "X-NotiDeck-Signature" in request.headers
    if provider == "signal":
        assert request.url.path == "/v2/send"


@pytest.mark.parametrize(
    "code,retryable", [(400, False), (401, False), (429, True), (503, True), (302, False)]
)
def test_classification_and_redaction(code, retryable, monkeypatch):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(code, json={"error": "SUPER-SECRET"}, headers={"Retry-After": "12"})
    )
    monkeypatch.setattr(
        "notideck.providers.builtin.safe_http", lambda timeout: httpx.Client(transport=transport)
    )
    result = Builtin("webhook").send(CONFIGS["webhook"], MESSAGE)
    assert result.success is False and result.retryable is retryable
    assert result.retry_after == 12
    assert "SUPER-SECRET" not in result.error


def test_smtp_real_adapter_fake_transport(monkeypatch):
    smtp = MagicMock()
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: smtp)
    smtp.__enter__.return_value.send_message.return_value = {}
    result = Builtin("email").send(
        {"host": "smtp.example.com", "port": 587, "from_address": "a@example.com", "to": "b@example.com"},
        MESSAGE,
    )
    assert result.success
    smtp.__enter__.return_value.starttls.assert_called_once()
    message = smtp.__enter__.return_value.send_message.call_args[0][0]
    assert message["Subject"] == "Alert"


def test_ssrf_blocks_private_at_connect(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 80))])
    with pytest.raises(ValueError, match="blocked"):
        SafeNetwork().connect_tcp("evil.example", 80)


def test_configuration_rejects_url_credentials():
    with pytest.raises(ValueError):
        Builtin("webhook").validate_configuration({"url": "https://user:password@example.com"})


def test_dns_pin_and_private_allowlist(monkeypatch):
    from notideck.security import allowed_ip

    monkeypatch.setenv("NOTIDECK_OUTBOUND_ALLOW_NETWORKS", "10.2.0.0/16")
    assert allowed_ip("10.2.0.1")
    assert not allowed_ip("169.254.169.254")
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    captured = []
    monkeypatch.setattr("httpcore.SyncBackend.connect_tcp", lambda self, host, *a: captured.append(host))
    SafeNetwork().connect_tcp("example.com", 443)
    assert captured == ["93.184.216.34"]


def test_webhook_template_and_timeout(monkeypatch):
    captured = []
    transport = httpx.MockTransport(
        lambda request: captured.append(json.loads(request.content)) or httpx.Response(202, json={})
    )
    monkeypatch.setattr(
        "notideck.providers.builtin.safe_http", lambda timeout: httpx.Client(transport=transport)
    )
    result = Builtin("webhook").send(
        {"url": "https://example.com", "payload": {"text": "{{ notification.title }}"}}, MESSAGE
    )
    assert result.success and captured == [{"text": "Alert"}]

    def timeout(request):
        raise httpx.ReadTimeout("secret URL must not escape")

    monkeypatch.setattr(
        "notideck.providers.builtin.safe_http",
        lambda timeout_: httpx.Client(transport=httpx.MockTransport(timeout)),
    )
    result = Builtin("webhook").send(CONFIGS["webhook"], MESSAGE)
    assert result.retryable and "secret" not in result.error


@pytest.mark.parametrize(
    "provider,config",
    [
        ("telegram", CONFIGS["telegram"]),
        ("slack", {"bot_token": "secret", "channel": "C1"}),
        ("whatsapp", CONFIGS["whatsapp"]),
        ("sms", CONFIGS["sms"]),
        ("signal", CONFIGS["signal"]),
    ],
)
def test_no_fabricated_acceptance_for_invalid_provider_response(provider, config, monkeypatch):
    monkeypatch.setattr(
        "notideck.providers.builtin.safe_http",
        lambda timeout: httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))
        ),
    )
    assert not Builtin(provider).send(config, MESSAGE).success


def test_signal_partial_error_not_success(monkeypatch):
    monkeypatch.setattr(
        "notideck.providers.builtin.safe_http",
        lambda timeout: httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    201, json={"timestamp": 123, "errors": {"recipient": "untrusted identity"}}
                )
            )
        ),
    )
    assert not Builtin("signal").send(CONFIGS["signal"], MESSAGE).success


@pytest.mark.parametrize(
    "failure,expected_code,retryable,diagnostic",
    [
        ("relay", "554", False, "relay access denied"),
        ("temporary_recipient", "450", True, "refused the recipient"),
        ("authentication", "535", False, "SMTP rejected request"),
        ("temporary_server", "451", True, "SMTP rejected request"),
        ("unsupported", None, False, "protocol or configuration"),
        ("disconnected", None, True, "disconnected"),
    ],
)
def test_smtp_failures_are_not_misreported_as_transport_timeouts(
    monkeypatch, failure, expected_code, retryable, diagnostic
):
    import smtplib

    failures = {
        "relay": smtplib.SMTPRecipientsRefused(
            {"private@example.test": (554, b"5.7.1 private@example.test: Relay access denied")}
        ),
        "temporary_recipient": smtplib.SMTPRecipientsRefused(
            {"private@example.test": (450, b"Mailbox unavailable")}
        ),
        "authentication": smtplib.SMTPAuthenticationError(535, b"secret provider details"),
        "temporary_server": smtplib.SMTPDataError(451, b"secret provider details"),
        "unsupported": smtplib.SMTPNotSupportedError("secret provider details"),
        "disconnected": smtplib.SMTPServerDisconnected("secret provider details"),
    }
    smtp = MagicMock()
    smtp.__enter__.return_value.send_message.side_effect = failures[failure]
    monkeypatch.setattr("smtplib.SMTP", lambda *args, **kwargs: smtp)
    result = Builtin("email").send(
        {
            "host": "smtp.example.test",
            "port": 25,
            "tls": "none",
            "from_address": "sender@example.test",
            "to": "private@example.test",
        },
        MESSAGE,
    )
    assert not result.success
    assert result.code == expected_code
    assert result.retryable is retryable
    assert diagnostic in result.error
    assert "secret" not in result.error and "private@example.test" not in result.error
