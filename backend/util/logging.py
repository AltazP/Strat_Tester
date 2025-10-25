import logging

def setup_logging(level: int = logging.INFO) -> None:
    fmt = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    logging.basicConfig(format=fmt, level=level, datefmt="%Y-%m-%d %H:%M:%S")

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)