import logging
from logging.handlers import TimedRotatingFileHandler

def setup_logger():
    rotador = TimedRotatingFileHandler(
        filename='inprint.log',
        when='D',
        interval=30,
        backupCount=6, 
        encoding='utf-8'
    )
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S', handlers=[rotador])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    return logging.getLogger("InPrint")

