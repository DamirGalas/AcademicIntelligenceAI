import logging
import sys
from pathlib import Path

import yaml


def setup_logger(name: str = "academic_intelligence_ai") -> logging.Logger:
    """Configure and return the application logger based on config.yaml."""
    config_path = Path(__file__).resolve().parents[3] / "config" / "config.yaml"

    log_level = "INFO"
    log_file = "logs/pipeline.log"

    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
        monitoring = config.get("monitoring", {})
        log_level = monitoring.get("log_level", log_level)
        log_file = monitoring.get("log_file", log_file)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """Get a child logger for a specific module.

    Usage in any module:
        from academic_intelligence_ai.monitoring.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Ingestion started")
    """
    setup_logger()
    return logging.getLogger(f"academic_intelligence_ai.{module_name}")
