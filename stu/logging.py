"""Loguru logging bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from .config import AppConfig


def setup_logging(config: AppConfig, logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_filename = Path(config.app.log_filename).name
    log_file = logs_dir / log_filename

    logger.remove()

    logger.add(
        sys.stderr,
        level=config.app.log_level.value,
        format=config.app.log_format,
    )

    logger.add(
        log_file,
        level=config.app.log_level.value,
        format=config.app.log_format,
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        enqueue=True,
    )

    logger.debug("Logging configured.")
