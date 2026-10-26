"""Private, atomic local configuration. Secrets never belong in the application DB."""

import json
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet
from filelock import FileLock
from platformdirs import user_data_path


def private_write(path: Path, text: str) -> None:
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    path.chmod(0o600)


class Config:
    def __init__(self, directory: str | Path | None = None):
        self.directory = Path(directory or os.getenv("NOTIDECK_CONFIG_DIR") or user_data_path("notideck"))
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = self.directory / "config.json"
        self.lock = FileLock(str(self.directory / "setup.lock"))
        with self.lock:
            key_path = self.directory / "master.key"
            key = os.getenv("NOTIDECK_MASTER_KEY")
            if not key:
                if not key_path.exists():
                    private_write(key_path, Fernet.generate_key().decode())
                key = key_path.read_text(encoding="utf-8").strip()
            self.cipher = Fernet(key.encode())
            self.token_path = self.directory / "bootstrap.token"
            if not self.token_path.exists():
                private_write(self.token_path, secrets.token_urlsafe(32))
        self.reload()

    def reload(self):
        self.values = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    @property
    def database_url(self):
        encrypted = self.values.get("database_url")
        return os.getenv("NOTIDECK_DATABASE_URL") or (self.decrypt(encrypted) if encrypted else None)

    def save_database(self, url: str):
        self.values["database_url"] = self.encrypt(url)
        private_write(self.path, json.dumps(self.values))

    def encrypt(self, value: str) -> str:
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self.cipher.decrypt(value.encode()).decode()

    @property
    def data_dir(self):
        path = Path(os.getenv("NOTIDECK_DATA_DIR", str(self.directory)))
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        return path
