import logging


LOGGING_LOG_FILE = f'logs/arbitrage.log'
LOGGING_FORMATTER_STRING = '%(asctime)s %(levelname)s %(message)s'


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.FileHandler(LOGGING_LOG_FILE, mode='a')
console_output = logging.StreamHandler()
formatter = logging.Formatter(LOGGING_FORMATTER_STRING)
handler.setFormatter(formatter)
console_output.setFormatter(formatter)
logger.addHandler(handler)
logger.addHandler(console_output)


if __name__ == '__main__':
    pass