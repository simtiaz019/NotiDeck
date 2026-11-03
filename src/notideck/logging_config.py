"""Shared file and console logging for independently supervised components."""

import logging
import os
from logging.handlers import RotatingFileHandler

from notideck.config import Config


class PrivateRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        stream = super()._open()
        if os.name != "nt":
            os.chmod(self.baseFilename, 0o600)
        return stream


def configure_logging(config: Config, component: str):
    """Write one component to its own rotating file while retaining console output."""
    directory = config.log_dir
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        directory.chmod(0o700)
    path = directory / f"{component}.log"
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_notideck_handler", False):
            root.removeHandler(handler)
            handler.close()

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(message)s"))
    console._notideck_handler = True  # type: ignore[attr-defined]
    file_handler = PrivateRotatingFileHandler(
        path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    file_handler._notideck_handler = True  # type: ignore[attr-defined]
    root.addHandler(console)
    root.addHandler(file_handler)
    root.setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return path
