"""Structured JSON logging configuration for AETHER."""

import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Custom JSON log formatter for structured output."""

    def format(self, record: logging.LogRecord) -> str:
        log_object = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_object)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure system-wide structured JSON logging."""
    logger = logging.getLogger()
    logger.setLevel(log_level.upper())

    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
