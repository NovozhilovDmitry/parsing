import threading
import time
from logs.log_settings import logger
from arbitrages.bingx import BingXWebSocket
from arbitrages.bybit import BybitWebSocket
from arbitrages.htx import HTXWebSocket
from arbitrages.okx import OKXWebSocket


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
ARBITRAGE_THRESHOLD = 0.002
TRADING_FEE = 0.001


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

threads = [
    threading.Thread(target=run_bingx, daemon=True),
    threading.Thread(target=run_bybit, daemon=True),
    threading.Thread(target=run_htx, daemon=True),
    threading.Thread(target=run_okx, daemon=True)
]

for thread in threads:
    thread.start()

def find_arbitrage_opportunities(prices):
    while True:
        for symbol, exchanges in prices.items():
            best_bid = None
            best_ask = None
            bid_exchange = None
            ask_exchange = None

            for exchange, data in exchanges.items():
                bid = data.get("bid")
                ask = data.get("ask")

                if bid and (best_bid is None or bid > best_bid):
                    best_bid = bid
                    bid_exchange = exchange

                if ask and (best_ask is None or ask < best_ask):
                    best_ask = ask
                    ask_exchange = exchange

            if best_bid and best_ask and best_bid > best_ask:
                profit_percent = (best_bid - best_ask) / best_ask

                net_profit_percent = profit_percent - 2 * TRADING_FEE
                if net_profit_percent > ARBITRAGE_THRESHOLD:
                    txt = f'''Монета: {symbol} с чистой прибылью {net_profit_percent * 100:.2f}%!
                    Купить на {ask_exchange} за {best_ask}
                    Продать на {bid_exchange} за {best_bid}'''
                    logger.info(txt)

        time.sleep(1)

arbitrage_thread = threading.Thread(target=find_arbitrage_opportunities, args=(prices_dict,), daemon=True)
arbitrage_thread.start()

while True:
    time.sleep(1)
