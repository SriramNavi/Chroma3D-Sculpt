"""Console logging without duplicate handlers after extension reloads."""

from __future__ import annotations

import logging

LOGGER_NAME = "chroma3d_sculpt"


def get_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not any(getattr(handler, "_chroma3d_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler._chroma3d_handler = True  # type: ignore[attr-defined]
        handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger

