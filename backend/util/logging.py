import logging
import os
from logging.handlers import RotatingFileHandler

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
  
  # Use rotating file handler if LOG_FILE is set, otherwise use stdout
  log_file = os.getenv("LOG_FILE")
  if log_file:
    # Rotate logs: 10MB per file, keep 5 backups (50MB total max)
    handler = RotatingFileHandler(
      log_file,
      maxBytes=10 * 1024 * 1024,  # 10MB
      backupCount=5,
      encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    logging.basicConfig(level=level, handlers=[handler])
  else:
    # Default: stdout (let systemd/journald handle rotation)
    logging.basicConfig(format=fmt, level=level, datefmt="%Y-%m-%d %H:%M:%S")

def get_logger(name: str) -> logging.Logger:
  return logging.getLogger(name)