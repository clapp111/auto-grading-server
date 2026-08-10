import json
import logging
import os
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> logging.Logger:
    app_logger = logging.getLogger("app")
    app_logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    app_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JsonFormatter())
    app_logger.addHandler(console_handler)
    app_logger.propagate = False
    return app_logger


logger = configure_logging()
