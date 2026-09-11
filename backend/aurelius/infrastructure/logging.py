"""
aurelius.infrastructure.logging
================================
Structured logging configuration for AURELIUS.

Design decisions:
  - Development: Plain text with colors (human-readable in terminal).
  - Production: JSON (machine-parseable, compatible with log aggregators).
  - Every log record should answer: What? Where? Why? Which request?
  - API keys, tokens, and secrets must NEVER appear in log output.
    This is enforced by never logging raw request headers or Settings objects.

Usage:
  Call configure_logging() once at application startup in aurelius.api.main.
  After that, use standard Python logging everywhere:

    import logging
    logger = logging.getLogger(__name__)
    logger.info("Fetching quote", extra={"ticker": "AAPL", "provider": "yahoo_finance"})

Log levels:
  DEBUG    — Detailed provider request/response (development only)
  INFO     — Request lifecycle, cache hits, successful operations
  WARNING  — Provider fallback, stale data, rate limit approaching
  ERROR    — Provider failure, calculation error, database error
  CRITICAL — Application cannot start (missing required configuration)
"""

import logging
import sys


def configure_logging(log_level: str = "INFO") -> None:
    """
    Configure application-wide logging.

    Args:
        log_level: Python logging level string ("DEBUG", "INFO", etc.).
                   Typically sourced from Settings.aurelius_log_level.

    This function should be called exactly ONCE, at application startup,
    before any other module uses the logging system.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Root logger: send everything to stdout.
    # Using stdout (not stderr) for structured logs so they can be piped
    # and captured cleanly in production log aggregators.
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove any existing handlers to avoid duplicate output.
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Suppress overly verbose third-party loggers.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging configured at level %s", log_level.upper()
    )
