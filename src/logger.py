"""Logging setup with dual handlers: console (INFO) + file (DEBUG)."""

import logging
from datetime import datetime
from pathlib import Path

from src.config import LOG_DIR

_root_logger: logging.Logger | None = None


def setup_logger() -> logging.Logger:
    """Create and configure the pipeline logger with console and file handlers.

    Returns:
        The configured root pipeline logger.
    """
    global _root_logger

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"pipeline_{timestamp}.log"

    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")

    # Console handler — INFO
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler — DEBUG
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    logger.info("Logger initialized. Log file: %s", log_file)

    _root_logger = logger
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger. Must be called after setup_logger().

    Args:
        name: Name for the child logger (e.g. module name).
    """
    return logging.getLogger(f"pipeline.{name}")
