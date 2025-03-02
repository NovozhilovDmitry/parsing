import logging, os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)
log_filename = os.path.join(LOGS_DIR, f'bot_log_{datetime.now().strftime("%Y%m%d")}.log')
wallet_log_filename = os.path.join(LOGS_DIR, f'wallet_{datetime.now().strftime("%Y%m%d")}.log')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s',
                    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()])

wallet_logger = logging.getLogger('wallet')
wallet_handler = logging.FileHandler(wallet_log_filename)
wallet_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
wallet_logger.setLevel(logging.INFO)
wallet_logger.addHandler(wallet_handler)

def log_event(message):
    logging.info(message)

def log_wallet(message):
    wallet_logger.info(message)
