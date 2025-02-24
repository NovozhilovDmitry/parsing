import json
import websocket
import threading
import time

# URL WebSocket Bybit
BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/spot"

# Монеты для подписки (нужно `orderbook.1.<pair>`)
PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
SUBSCRIPTIONS = {"op": "subscribe", "args": [f"orderbook.1.{pair}" for pair in PAIRS]}

# Словарь для хранения цен
bybit_prices = {pair: {"bid": None, "ask": None} for pair in PAIRS}


# Класс WebSocket для Bybit
class BybitWebSocket:
    def __init__(self):
        self.ws = None

    # Подключение к WebSocket
    def on_open(self, ws):
        print("✅ Подключено к WebSocket Bybit")
        ws.send(json.dumps(SUBSCRIPTIONS))
        print("📡 Подписка отправлена:", SUBSCRIPTIONS)

    # Получение сообщений
    def on_message(self, ws, message):
        try:
            data = json.loads(message)

            if "success" in data and data["success"]:
                print(f"🔔 Подписка успешна: {data}")
                return

            if "topic" in data and "orderbook" in data["topic"]:
                orderbook_data = data["data"]
                symbol = orderbook_data["s"]
                bids = orderbook_data.get("b", [])
                asks = orderbook_data.get("a", [])

                # Извлекаем лучшие цены
                if bids and asks:
                    bid_price = float(bids[0][0])  # Лучшая цена покупки
                    ask_price = float(asks[0][0])  # Лучшая цена продажи

                    if symbol in bybit_prices:
                        bybit_prices[symbol]["bid"] = bid_price
                        bybit_prices[symbol]["ask"] = ask_price
                        print(f"Bybit | {symbol} | Bid: {bid_price} | Ask: {ask_price}")

        except Exception as e:
            print(f"❌ Ошибка обработки данных Bybit: {e}")

    # Обработка ошибок
    def on_error(self, ws, error):
        print(f"❌ Ошибка WebSocket Bybit: {error}")

    # Закрытие соединения
    def on_close(self, ws, close_status_code, close_msg):
        print("❌ WebSocket Bybit закрыт")

    # Запуск WebSocket с автоматическим восстановлением
    def start(self):
        while True:
            try:
                self.ws = websocket.WebSocketApp(
                    BYBIT_WS_URL,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                )
                self.ws.run_forever()
            except Exception as e:
                print(f"❌ Ошибка WebSocket Bybit (перезапуск): {e}")
            time.sleep(5)  # Ждём перед повторным подключением


# Запуск в отдельном потоке
def run_bybit_websocket():
    bybit_ws = BybitWebSocket()  # Создаём объект WebSocket
    bybit_ws.start()  # Запускаем

if __name__ == '__main__':
    bybit_thread = threading.Thread(target=run_bybit_websocket, daemon=True)
    bybit_thread.start()

    # Поддерживаем основной поток активным
    while True:
        time.sleep(1)
