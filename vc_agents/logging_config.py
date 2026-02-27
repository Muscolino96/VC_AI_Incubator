"""Structured logging configuration for the VC AI Incubator pipeline."""

from __future__ import annotations

import logging
import sys
from typing import Any


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure and return the root pipeline logger."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s | %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))

    logger = logging.getLogger("vc_agents")
    logger.setLevel(level)
    if not logger.handlers:
        logger.addHandler(handler)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the vc_agents namespace."""
    return logging.getLogger(f"vc_agents.{name}")


def log_api_call(
    logger: logging.Logger,
    *,
    provider: str,
    stage: str,
    idea_id: str = "",
    attempt: int = 1,
    latency_ms: float = 0,
    success: bool = True,
    error: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    """Log a structured API call event."""
    parts = [f"provider={provider}", f"stage={stage}"]
    if idea_id:
        parts.append(f"idea_id={idea_id}")
    parts.append(f"attempt={attempt}")
    if latency_ms:
        parts.append(f"latency_ms={latency_ms:.0f}")
    if error:
        parts.append(f"error={error}")
    if extra:
        for k, v in extra.items():
            parts.append(f"{k}={v}")

    msg = " | ".join(parts)
    if success:
        logger.info(msg)
    else:
        logger.warning(msg)
