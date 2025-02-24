import json
import websocket
import threading
import time

# URL WebSocket OKX
OKX_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"

# Монеты для подписки
PAIRS = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT"]
SUBSCRIPTIONS = [{"op": "subscribe", "args": [{"channel": "tickers", "instId": pair}]} for pair in PAIRS]

# Словарь для хранения цен
okx_prices = {pair: {"bid": None, "ask": None} for pair in PAIRS}


# Класс WebSocket для OKX
class OKXWebSocket:
    def __init__(self):
        self.ws = None

    # Подключение к WebSocket
    def on_open(self, ws):
        print("✅ Подключено к WebSocket OKX")
        for sub in SUBSCRIPTIONS:
            ws.send(json.dumps(sub))
            print("📡 Подписка отправлена:", sub)

    # Получение сообщений
    def on_message(self, ws, message):
        try:
            data = json.loads(message)

            if "event" in data and data["event"] == "subscribe":
                print(f"🔔 Подписка успешна: {data}")
                return

            if "arg" in data and "data" in data:
                ticker_data = data["data"][0]
                symbol = data["arg"]["instId"]
                bid_price = float(ticker_data["bidPx"])
                ask_price = float(ticker_data["askPx"])

                if symbol in okx_prices:
                    okx_prices[symbol]["bid"] = bid_price
                    okx_prices[symbol]["ask"] = ask_price
                    print(f"OKX | {symbol} | Bid: {bid_price} | Ask: {ask_price}")

        except Exception as e:
            print(f"❌ Ошибка обработки данных OKX: {e}")

    # Обработка ошибок
    def on_error(self, ws, error):
        print(f"❌ Ошибка WebSocket OKX: {error}")

    # Закрытие соединения
    def on_close(self, ws, close_status_code, close_msg):
        print("❌ WebSocket OKX закрыт")

    # Запуск WebSocket с автоматическим восстановлением
    def start(self):
        while True:
            try:
                self.ws = websocket.WebSocketApp(
                    OKX_WS_URL,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                )
                self.ws.run_forever()
            except Exception as e:
                print(f"❌ Ошибка WebSocket OKX (перезапуск): {e}")
            time.sleep(5)  # Ждём перед повторным подключением


# Запуск в отдельном потоке
def run_okx_websocket():
    okx_ws = OKXWebSocket()  # Создаём объект WebSocket
    okx_ws.start()  # Запускаем


if __name__ == '__main__':
    okx_thread = threading.Thread(target=run_okx_websocket, daemon=True)
    okx_thread.start()

    # Поддерживаем основной поток активным
    while True:
        time.sleep(1)
