import hashlib
import ipaddress
import os
import re
import socket
import time

import httpcore
import httpx
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from notideck.database.models import RateBucket

hasher = PasswordHasher()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password: str):
    minimum = max(12, int(os.getenv("NOTIDECK_PASSWORD_MIN_LENGTH", "12")))
    if (
        len(password) < minimum
        or len(password) > 256
        or not re.search(r"[A-Za-z]", password)
        or not re.search(r"[^A-Za-z]", password)
    ):
        raise ValueError(f"Password must contain letters and nonletters and be {minimum}–256 characters")
    return hasher.hash(password)


def verify_password(stored: str, value: str):
    try:
        return hasher.verify(stored, value)
    except VerificationError:
        return False


def consume_rate(factory, key: str, limit: int, seconds: int = 60):
    """Shared, atomic fixed-window limits across server processes."""
    window = int(time.time()) // seconds
    with factory() as db:
        db.execute(
            update(RateBucket)
            .where(RateBucket.key == key, RateBucket.window != window)
            .values(window=window, count=0)
        )
        result = db.execute(
            update(RateBucket)
            .where(RateBucket.key == key, RateBucket.window == window, RateBucket.count < limit)
            .values(count=RateBucket.count + 1)
        )
        if result.rowcount:
            db.commit()
            return True
        if db.get(RateBucket, key):
            db.rollback()
            return False
        db.add(RateBucket(key=key, window=window, count=1))
        try:
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
    return consume_rate(factory, key, limit, seconds)


def allowed_ip(value: str):
    ip = ipaddress.ip_address(value.split("%")[0])
    if ip.is_global:
        return True
    return any(
        ip in ipaddress.ip_network(c.strip())
        for c in os.getenv("NOTIDECK_OUTBOUND_ALLOW_NETWORKS", "").split(",")
        if c.strip()
    )


class SafeNetwork(httpcore.SyncBackend):
    """Pin the validated DNS address at connection time; preserve hostname for TLS/SNI."""

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        if not addresses or any(not allowed_ip(str(a[4][0])) for a in addresses):
            raise ValueError("Outbound destination blocked by network policy")
        return super().connect_tcp(str(addresses[0][4][0]), port, timeout, local_address, socket_options)


def safe_http(timeout=15):
    transport = httpx.HTTPTransport(retries=0)
    transport._pool._network_backend = SafeNetwork()
    return httpx.Client(
        transport=transport, timeout=httpx.Timeout(timeout), follow_redirects=False, trust_env=False
    )
