
import logging
from logging.handlers import TimedRotatingFileHandler

def setup_logging():
    logger = logging.getLogger("dtu_hub")
    logger.setLevel(logging.INFO)
    handler = TimedRotatingFileHandler(
        "./log/dtu_hub.log", when="midnight", interval=1, backupCount=30)
    handler.suffix = "%Y%m%d"
    handler.maxBytes = 10 * 1024 * 1024  # 10MB
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger