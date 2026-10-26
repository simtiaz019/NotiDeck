import hashlib
import hmac
import json
import re
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx

from notideck.security import safe_http
from notideck.routing import render
from . import Result


class Builtin:
    fields = {
        "telegram": ["bot_token", "chat_id"],
        "email": ["host", "port", "from_address", "to"],
        "slack": ["webhook_url"],
        "discord": ["webhook_url"],
        "webhook": ["url"],
        "whatsapp": [
            "access_token",
            "phone_number_id",
            "recipient",
            "api_version",
            "template_name",
            "language",
        ],
        "sms": ["account_sid", "auth_token", "from_number", "to"],
        "signal": ["url", "account", "recipient"],
    }
    optional = {
        "telegram": ["parse_mode"],
        "email": ["username", "password", "tls", "cc", "bcc"],
        "slack": ["bot_token", "channel"],
        "discord": [],
        "webhook": [
            "method",
            "headers",
            "bearer_token",
            "basic_username",
            "basic_password",
            "hmac_secret",
            "payload",
        ],
        "whatsapp": ["components"],
        "sms": [],
        "signal": [],
    }

    def __init__(self, provider_type):
        self.provider_type = provider_type

    def configuration_schema(self):
        keys = self.fields[self.provider_type] + self.optional[self.provider_type] + ["timeout"]
        return {
            "type": "object",
            "required": self.fields[self.provider_type],
            "properties": {key: {"type": "string", "secret": self.is_secret(key)} for key in keys},
        }

    @staticmethod
    def is_secret(key):
        return any(s in key for s in ["token", "secret", "password", "webhook_url", "headers"])

    def supported_capabilities(self):
        return ["text", "test_send"] + (["html"] if self.provider_type == "email" else [])

    def validate_configuration(self, config):
        config = dict(config)
        required = self.fields[self.provider_type]
        if self.provider_type == "slack" and config.get("bot_token"):
            required = ["bot_token", "channel"]
        if any(not config.get(key) for key in required):
            raise ValueError("Missing provider fields: " + ", ".join(required))
        config["timeout"] = float(config.get("timeout", 15))
        if not 1 <= config["timeout"] <= 30:
            raise ValueError("Timeout must be between 1 and 30 seconds")
        for key in ["url", "webhook_url"]:
            if config.get(key):
                url = urlsplit(config[key])
                if (
                    url.scheme not in {"http", "https"}
                    or not url.hostname
                    or url.username
                    or url.password
                    or url.fragment
                ):
                    raise ValueError("Destination must be an HTTP(S) URL without userinfo or fragment")
        for key in ["phone_number_id", "api_version", "account_sid"]:
            if config.get(key) and not re.fullmatch(r"[A-Za-z0-9.]+", config[key]):
                raise ValueError(f"Invalid {key}")
        if self.provider_type == "email":
            config["port"] = int(config["port"])
            if config.get("tls", "starttls") not in {"starttls", "tls", "none"}:
                raise ValueError("SMTP TLS must be starttls, tls, or none")
        if self.provider_type == "webhook" and config.get("method", "POST") not in {"POST", "PUT", "PATCH"}:
            raise ValueError("Webhook method must be POST, PUT or PATCH")
        return config

    def test_connection(self, config):
        return self.send(
            config,
            {
                "title": "NotiDeck channel test",
                "message": "This is a real test notification.",
                "severity": "INFO",
                "id": "test",
                "environment": "test",
            },
        )

    def send(self, config, message, recipient=None):
        try:
            c = self.validate_configuration(config)
            if self.provider_type == "email":
                return self._email(c, message, recipient)
            return self._http(c, message, recipient)
        except smtplib.SMTPRecipientsRefused as exc:
            # SMTPException inherits OSError: handle SMTP failures before transport failures.
            refusals = list(exc.recipients.values())
            codes = [int(code) for code, _ in refusals]
            relay_denied = any(
                b"relay access denied" in (reply if isinstance(reply, bytes) else str(reply).encode()).lower()
                for _, reply in refusals
            )
            retryable = bool(codes) and all(400 <= code < 500 for code in codes)
            code = next((code for code in codes if code >= 500), codes[0] if codes else None)
            return Result(
                False,
                retryable,
                code=str(code) if code is not None else None,
                error=(
                    "SMTP relay access denied; ask the mail administrator to authorize this sender "
                    "and application host for the recipient, or configure an authenticated SMTP relay"
                    if relay_denied
                    else "SMTP server refused the recipient; check the address and server relay permissions"
                ),
            )
        except smtplib.SMTPResponseException as exc:
            return Result(
                False, 400 <= exc.smtp_code < 500, code=str(exc.smtp_code), error="SMTP rejected request"
            )
        except smtplib.SMTPServerDisconnected:
            return Result(False, True, error="SMTP server disconnected before completing the request")
        except smtplib.SMTPException:
            return Result(False, error="SMTP protocol or configuration error; review channel settings")
        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            TimeoutError,
            OSError,
        ):
            return Result(False, True, error="Transport unavailable or timed out")
        except (ValueError, TypeError, KeyError):
            return Result(False, error="Invalid provider configuration or response; review channel settings")

    def _email(self, c, m, recipient):
        msg = EmailMessage()
        msg["Subject"] = m["title"]
        msg["From"] = c["from_address"]
        msg["To"] = recipient or c["to"]
        if c.get("cc"):
            msg["Cc"] = c["cc"]
        if c.get("bcc"):
            msg["Bcc"] = c["bcc"]
        msg.set_content(m["message"])
        if m.get("html"):
            msg.add_alternative(m["html"], subtype="html")
        mode = c.get("tls", "starttls")
        cls = smtplib.SMTP_SSL if mode == "tls" else smtplib.SMTP
        kwargs = {"timeout": c["timeout"]}
        if mode == "tls":
            kwargs["context"] = ssl.create_default_context()
        with cls(c["host"], c["port"], **kwargs) as smtp:
            if mode == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            if c.get("username"):
                smtp.login(c["username"], c.get("password", ""))
            refused = smtp.send_message(msg)
            if refused:
                return Result(False, False, error="SMTP refused one or more recipients")
        return Result(True, accepted_at=time.time())

    def _http(self, c, m, recipient):
        p = self.provider_type
        content = f"[{m['severity']}] {m['title']}\n{m['message']}"
        headers = {}
        method = "POST"
        auth = None
        data = None
        body = None
        colors = {
            "DEBUG": "#7c8a96",
            "INFO": "#4488cc",
            "WARNING": "#d5a030",
            "ERROR": "#d56b40",
            "CRITICAL": "#c54242",
        }

        def interpolate(value):
            if isinstance(value, str):
                return render(value, m)
            if isinstance(value, list):
                return [interpolate(item) for item in value]
            if isinstance(value, dict):
                return {key: interpolate(item) for key, item in value.items()}
            return value

        if p == "telegram":
            url = f"https://api.telegram.org/bot{c['bot_token']}/sendMessage"
            payload = {"chat_id": recipient or c["chat_id"], "text": content}
            if c.get("parse_mode"):
                payload["parse_mode"] = c["parse_mode"]
        elif p == "slack":
            url = c.get("webhook_url") or "https://slack.com/api/chat.postMessage"
            payload = {
                "text": content,
                "attachments": [{"color": colors.get(m["severity"], "#7c8a96"), "text": m["message"]}],
            }
            if c.get("bot_token"):
                url = "https://slack.com/api/chat.postMessage"
                headers["Authorization"] = "Bearer " + c["bot_token"]
                payload["channel"] = recipient or c["channel"]
        elif p == "discord":
            url = c["webhook_url"]
            payload = {
                "embeds": [
                    {
                        "title": m["title"],
                        "description": m["message"],
                        "color": int(colors.get(m["severity"], "#7c8a96")[1:], 16),
                    }
                ],
                "allowed_mentions": {"parse": []},
            }
        elif p == "whatsapp":
            url = f"https://graph.facebook.com/{c['api_version']}/{c['phone_number_id']}/messages"
            headers["Authorization"] = "Bearer " + c["access_token"]
            payload = {
                "messaging_product": "whatsapp",
                "to": recipient or c["recipient"],
                "type": "template",
                "template": {
                    "name": c["template_name"],
                    "language": {"code": c["language"]},
                    "components": interpolate(c.get("components", [])),
                },
            }
        elif p == "sms":
            url = f"https://api.twilio.com/2010-04-01/Accounts/{c['account_sid']}/Messages.json"
            auth = (c["account_sid"], c["auth_token"])
            data = {"To": recipient or c["to"], "From": c["from_number"], "Body": content}
            payload = None
        elif p == "signal":
            url = c["url"].rstrip("/") + "/v2/send"
            payload = {
                "number": c["account"],
                "recipients": [recipient or c["recipient"]],
                "message": content,
            }
        else:
            url = c["url"]
            method = c.get("method", "POST")
            headers = dict(c.get("headers", {}))
            if any(k.lower() in {"host", "content-length", "transfer-encoding"} for k in headers):
                raise ValueError("Unsafe header")
            if c.get("bearer_token"):
                headers["Authorization"] = "Bearer " + c["bearer_token"]
            if c.get("basic_username"):
                auth = (c["basic_username"], c.get("basic_password", ""))
            payload = interpolate(c["payload"]) if c.get("payload") else m
            body = json.dumps(payload, ensure_ascii=False).encode()
            headers["Content-Type"] = "application/json"
            if c.get("hmac_secret"):
                headers["X-NotiDeck-Signature"] = hmac.new(
                    c["hmac_secret"].encode(), body, hashlib.sha256
                ).hexdigest()
        deadline = time.monotonic() + c["timeout"]
        with safe_http(c["timeout"]) as client:
            with client.stream(
                method,
                url,
                headers=headers,
                auth=auth,
                json=payload if body is None and data is None else None,
                content=body,
                data=data,
            ) as response:
                raw = bytearray()
                for chunk in response.iter_bytes():
                    if time.monotonic() > deadline:
                        raise httpx.ReadTimeout("Provider response deadline exceeded")
                    raw.extend(chunk)
                    if len(raw) > 65536:
                        raise ValueError("Provider response exceeds limit")
                try:
                    result = json.loads(raw) if raw else {}
                except ValueError:
                    result = {}
                if not isinstance(result, dict):
                    result = {}
                ok = 200 <= response.status_code < 300 and result.get("ok", True) is not False
                if p == "telegram" or (p == "slack" and c.get("bot_token")):
                    ok = ok and result.get("ok") is True
                if p == "whatsapp":
                    ok = ok and bool(result.get("messages"))
                if p == "sms":
                    ok = ok and bool(result.get("sid"))
                if p == "signal":
                    ok = ok and bool(result.get("timestamp")) and not result.get("errors")
                retry_after = response.headers.get("Retry-After") or result.get("parameters", {}).get(
                    "retry_after"
                )
                if p == "discord":
                    retry_after = retry_after or result.get("retry_after")
                if retry_after:
                    try:
                        retry_after = max(0, float(retry_after))
                    except ValueError:
                        retry_after = max(0, parsedate_to_datetime(retry_after).timestamp() - time.time())
                code = result.get("error_code", response.status_code)
                message_id = result.get("sid") or result.get("ts") or result.get("id")
                if p == "telegram":
                    message_id = result.get("result", {}).get("message_id")
                if p == "whatsapp" and result.get("messages"):
                    message_id = result["messages"][0].get("id")
                retryable = code in {408, 425, 429} or (isinstance(code, int) and code >= 500)
                if p == "slack" and result.get("error") in {
                    "ratelimited",
                    "rate_limited",
                    "internal_error",
                    "fatal_error",
                    "service_unavailable",
                }:
                    retryable = True
                if p == "signal":
                    message_id = result.get("timestamp")
                return Result(
                    ok,
                    retryable,
                    str(message_id)[:255] if message_id else None,
                    str(code)[:50],
                    None if ok else "Provider rejected request; response body redacted",
                    retry_after,
                    time.time() if ok else None,
                )
