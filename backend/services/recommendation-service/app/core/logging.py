import logging
import sys

def setup_logging():
    level = logging.INFO
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=level, format=fmt, stream=sys.stdout)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
