"""Structured JSON logging (ported from swap-service).

Convention everywhere: `logger.info("event_slug", extra={"data": {...}})`. The
message is a short event slug; structured fields go in `extra={"data": ...}`. NEVER
log headers, tokens, API keys, or request/response bodies.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

_CONFIGURED = False


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        data = getattr(record, "data", None)
        if data:
            payload["data"] = data
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Idempotently install a single stdout JSON handler on the root logger."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    _CONFIGURED = True


def get_logger(module: str) -> logging.Logger:
    """Namespaced logger: `storybook-storage.<module>`."""
    return logging.getLogger(f"storybook-storage.{module}")
