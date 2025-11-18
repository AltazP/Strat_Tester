import logging
import os

def setup_logging(level: int = None) -> None:
  if level is None:
    level_str = os.getenv("LOG_LEVEL", "WARNING").upper()
    level_map = {
      "DEBUG": logging.DEBUG,
      "INFO": logging.INFO,
      "WARNING": logging.WARNING,
      "ERROR": logging.ERROR,
      "CRITICAL": logging.CRITICAL,
    }
    level = level_map.get(level_str, logging.WARNING)
  
  fmt = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
  logging.basicConfig(format=fmt, level=level, datefmt="%Y-%m-%d %H:%M:%S")

def get_logger(name: str) -> logging.Logger:
  return logging.getLogger(name)