import json
import websocket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from logs.logging import logger
from algoritmic_functions import build_graph, bellman_ford
from functions import  calculate_arbitrage_profit


# URL для WebSocket
WS_URL = "wss://stream.bybit.com/v5/public/spot"
PAIRS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'TRUMPUSDT', 'PNUTUSDT', 'SUIUSDT', 'KAITOUSDT',
         'LTCUSDT', 'IPUSDT', '1000PEPEUSDT', 'WIFUSDT', 'BANUSDT', 'FARTCOINUSDT']
BASE_CURRENCY = "USDT"  # Базовая валюта
FEE_RATE = 0.001  # Комиссия 0.1%
MIN_LIQUIDITY = 1.0  # Минимальный объем сделки в USDT
prices = {pair: {"bid": None, "ask": None, "bidSize": None, "askSize": None} for pair in PAIRS}

# url = 'wss://stream-testnet.bybit.com/v5/private'
# uri = 'wss://stream-testnet.bybit.com/v5/trade'

# Функция обработки входящих сообщений
def on_message(ws, message):
    data = json.loads(message)
    symbol_tag = data.get('data')

    if symbol_tag and isinstance(data["data"], dict):
        symbol = symbol_tag.get('symbol')

        bid_price = symbol_tag.get("bidPrice")
        ask_price = symbol_tag.get("askPrice")
        bid_size = symbol_tag.get("bidSize")
        ask_size = symbol_tag.get("askSize")
        last_price = symbol_tag.get("lastPrice")

        if symbol in prices:
            try:
                # Если bidPrice и askPrice отсутствуют, используем lastPrice
                if bid_price is None and last_price is not None:
                    bid_price = float(last_price) * 0.999
                if ask_price is None and last_price is not None:
                    ask_price = float(last_price) * 1.001

                # Записываем обновлённые цены
                prices[symbol]["bid"] = float(bid_price) if bid_price is not None else None
                prices[symbol]["ask"] = float(ask_price) if ask_price is not None else None
                prices[symbol]["bidSize"] = float(bid_size) if bid_size is not None else 0.0
                prices[symbol]["askSize"] = float(ask_size) if ask_size is not None else 0.0

            except ValueError:
                print(f"⚠️ Ошибка преобразования данных для {symbol}: {data['data']}")
        else:
            print(f"⚠️ Символ {symbol} не найден в списке монет.")

# Функция обработки ошибок
def on_error(ws, error):
    print(f"Ошибка: {error}")

# Функция обработки закрытия соединения
def on_close(ws, close_status_code, close_msg):
    print("Соединение закрыто")
    print(f'{close_status_code}: {close_msg}')

# Функция обработки успешного подключения
def on_open(ws):
    print("Подключено к Bybit WebSocket")
    subscribe_msg = {
        "op": "subscribe",
        "args": [f"tickers.{pair}" for pair in PAIRS]
    }
    ws.send(json.dumps(subscribe_msg))

# Запуск WebSocket в отдельном потоке
def run_websocket():
    ws = websocket.WebSocketApp(WS_URL, on_message=on_message, on_error=on_error, on_close=on_close)
    ws.on_open = on_open
    ws.run_forever()

# Потоковый анализ арбитража
def analyze_arbitrage():
    while True:
        graph = build_graph(prices, BASE_CURRENCY, FEE_RATE, MIN_LIQUIDITY)

        with ThreadPoolExecutor(max_workers=4) as executor:
            future = executor.submit(bellman_ford, graph, BASE_CURRENCY)
            cycle = future.result()

        if cycle:
            profit = calculate_arbitrage_profit(cycle, prices, FEE_RATE, MIN_LIQUIDITY)
            if profit == 0:
                print("❌ Цикл найден, но ликвидность недостаточна!")
            else:
                logger.info("🔴 Найден арбитражный цикл! 🔄", " → ".join(cycle))
                print(f"💰 Потенциальная прибыль: {profit:.4f} USDT")

                if profit > 1.01:
                    logger.info('🚀 Арбитраж выгоден! Стоит действовать!')
                else:
                    logger.warning('⚠️ После учёта всех факторов прибыль мала. Пропускаем.')
        else:
            print(f"⚪ Арбитраж не найден")

        time.sleep(4)

# Запуск WebSocket
ws_thread = threading.Thread(target=run_websocket, daemon=True)
ws_thread.start()

# Запускаем арбитражный анализ в отдельном потоке
arb_thread = threading.Thread(target=analyze_arbitrage, daemon=True)
arb_thread.start()

# Оставляем программу работать
while True:
    time.sleep(1)
