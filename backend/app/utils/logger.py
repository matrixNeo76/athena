"""
ATHENA Structured Logging
==========================
JSON-formatted logging with job_id context binding.
Writes to stdout (INFO+) and the logs/ directory (DEBUG+).
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Log directory ─────────────────────────────
LOG_DIR = Path(os.getenv(
    "LOG_DIR",
    "/mnt/efs/spaces/20dcf961-555e-43d9-be93-e854755ce10c/b89d840c-0d1d-4454-b7ee-1364b4a91fab/logs"
))
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ── Formatter ────────────────────────────────

class JSONFormatter(logging.Formatter):
    """Formats log records as newline-delimited JSON."""

    # Fields from LogRecord that we don't want to re-emit as extras
    _SKIP = frozenset({
        "message", "asctime", "name", "msg", "args", "levelname",
        "levelno", "pathname", "filename", "module", "exc_info",
        "exc_text", "stack_info", "lineno", "funcName", "created",
        "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process",
    })

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
            "module":    record.module,
            "func":      record.funcName,
            "line":      record.lineno,
        }
        # Inject any extra fields (e.g. job_id)
        for key, val in record.__dict__.items():
            if key not in self._SKIP and not key.startswith("_"):
                log_entry[key] = val

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


# ── Context adapter ───────────────────────────

class JobContextAdapter(logging.LoggerAdapter):
    """Logger adapter that injects job_id into every log record."""

    def process(self, msg: str, kwargs: dict) -> tuple:
        kwargs.setdefault("extra", {})
        kwargs["extra"]["job_id"] = self.extra.get("job_id", "")
        return msg, kwargs


# ── Public API ────────────────────────────────

def get_logger(
    name: str,
    job_id: Optional[str] = None,
) -> logging.Logger | JobContextAdapter:
    """
    Return a configured JSON logger.

    Args:
        name:    Logger name (typically __name__).
        job_id:  Optional job identifier injected into all log entries.
    """
    base_logger = logging.getLogger(name)
    if not base_logger.handlers:
        _attach_handlers(base_logger)

    if job_id:
        return JobContextAdapter(base_logger, {"job_id": job_id})
    return base_logger


def setup_root_logging(level: str = "INFO") -> None:
    """
    Call once at application startup to configure the root logger.

    Args:
        level: Log level string ('DEBUG', 'INFO', 'WARNING', 'ERROR').
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    # Stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(JSONFormatter())
    stdout_handler.setLevel(logging.INFO)
    root.addHandler(stdout_handler)

    # Aggregated file handler
    file_handler = logging.FileHandler(LOG_DIR / "athena-all.log", encoding="utf-8")
    file_handler.setFormatter(JSONFormatter())
    file_handler.setLevel(logging.DEBUG)
    root.addHandler(file_handler)


# ── Internal ──────────────────────────────────

def _attach_handlers(logger: logging.Logger) -> None:
    """Attach stdout + file handlers to a named logger."""
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(JSONFormatter())
    stdout_handler.setLevel(logging.INFO)
    logger.addHandler(stdout_handler)

    file_handler = logging.FileHandler(LOG_DIR / "athena.log", encoding="utf-8")
    file_handler.setFormatter(JSONFormatter())
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
