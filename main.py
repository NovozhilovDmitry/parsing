import threading
import time
from logs.logging import logger
from bingx import BingXWebSocket
from bybit import BybitWebSocket
from htx import HTXWebSocket
from okx import OKXWebSocket

# Словарь для хранения цен
prices_dict = {
    'BTCUSDT': {},
    'ETHUSDT': {},
    'SOLUSDT': {},
    'XRPUSDT': {},
    'DOGEUSDT': {},
    'SUIUSDT': {},
    'LTCUSDT': {},
    'IPUSDT': {},
    'ADAUSDT': {},
    'TONUSDT': {}
}

# Порог прибыли для арбитража (например, 0.2%)
ARBITRAGE_THRESHOLD = 0.002  # 0.2% в десятичной форме
TRADING_FEE = 0.001  # 0.1% комиссия за сделку


# Функции для запуска WebSocket
def run_bingx():
    print("🔹 Запускаем BingX WebSocket")
    bingx_ws = BingXWebSocket(prices_dict)
    bingx_ws.start()

def run_bybit():
    print("🔹 Запускаем Bybit WebSocket")
    bybit_ws = BybitWebSocket(prices_dict)
    bybit_ws.start()

def run_htx():
    print("🔹 Запускаем HTX WebSocket")
    htx_ws = HTXWebSocket(prices_dict)
    htx_ws.start()

def run_okx():
    print("🔹 Запускаем OKX WebSocket")
    okx_ws = OKXWebSocket(prices_dict)
    okx_ws.start()


# Запуск в потоках
threads = [
    threading.Thread(target=run_bingx, daemon=True),
    threading.Thread(target=run_bybit, daemon=True),
    threading.Thread(target=run_htx, daemon=True),
    threading.Thread(target=run_okx, daemon=True),
]

for thread in threads:
    thread.start()

# Функция поиска арбитражных возможностей
def find_arbitrage_opportunities(prices):
    while True:
        for symbol, exchanges in prices.items():
            best_bid = None
            best_ask = None
            bid_exchange = None
            ask_exchange = None

            # Поиск лучшей цены покупки (ask) и продажи (bid)
            for exchange, data in exchanges.items():
                bid = data.get("bid")
                ask = data.get("ask")

                if bid and (best_bid is None or bid > best_bid):
                    best_bid = bid
                    bid_exchange = exchange

                if ask and (best_ask is None or ask < best_ask):
                    best_ask = ask
                    ask_exchange = exchange

            # Проверяем возможность арбитража
            if best_bid and best_ask and best_bid > best_ask:
                profit_percent = (best_bid - best_ask) / best_ask

                # Учитываем комиссию (две сделки — покупка и продажа)
                net_profit_percent = profit_percent - 2 * TRADING_FEE
                if net_profit_percent > ARBITRAGE_THRESHOLD:
                    txt = f'''Монета: {symbol} с чистой прибылью {net_profit_percent * 100:.2f}%!
                    Купить на {ask_exchange} за {best_ask}
                    Продать на {bid_exchange} за {best_bid}'''
                    logger.info(txt)

        time.sleep(1)  # Проверка каждую секунду

# Запускаем поиск арбитража в отдельном потоке
arbitrage_thread = threading.Thread(target=find_arbitrage_opportunities, args=(prices_dict,), daemon=True)
arbitrage_thread.start()

# Поддерживаем основной поток активным
while True:
    time.sleep(1)
