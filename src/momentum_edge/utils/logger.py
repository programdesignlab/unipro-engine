"""Loguru logger configured from settings."""

import sys
from loguru import logger
from momentum_edge.config import settings

logger.remove()
logger.add(sys.stderr, level=settings.log_level, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>")
logger.add("logs/momentum_edge.log", level="DEBUG", rotation="10 MB", retention="30 days", compression="zip")
