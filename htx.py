import json
import websocket
import threading
import time
import gzip

# URL WebSocket HTX
HTX_WS_URL = "wss://api.huobi.pro/ws"

# Монеты для подписки (формат HTX: `market.<pair>.depth.step0`)
PAIRS = ["btcusdt", "ethusdt", "solusdt", "xrpusdt", "dogeusdt"]
SUBSCRIPTIONS = [{"sub": f"market.{pair}.depth.step0", "id": pair} for pair in PAIRS]

# Словарь для хранения цен
htx_prices = {pair: {"bid": None, "ask": None} for pair in PAIRS}


# Класс WebSocket для HTX
class HTXWebSocket:
    def __init__(self):
        self.ws = None

    # Подключение к WebSocket
    def on_open(self, ws):
        print("✅ Подключено к WebSocket HTX")
        for sub in SUBSCRIPTIONS:
            ws.send(json.dumps(sub))
            print("📡 Подписка отправлена:", sub)

    # Декодирование Gzip
    def decode_message(self, message):
        return gzip.decompress(message).decode("utf-8")

    # Получение сообщений
    def on_message(self, ws, message):
        try:
            utf8_data = self.decode_message(message)
            data = json.loads(utf8_data)

            if "ping" in data:  # Отвечаем на пинг
                ws.send(json.dumps({"pong": data["ping"]}))

            if "tick" in data and "bids" in data["tick"] and "asks" in data["tick"]:
                symbol = data["ch"].split(".")[1]  # Извлекаем символ из `ch`
                bid_price = float(data["tick"]["bids"][0][0])  # Лучшая цена покупки
                ask_price = float(data["tick"]["asks"][0][0])  # Лучшая цена продажи

                if symbol in htx_prices:
                    htx_prices[symbol]["bid"] = bid_price
                    htx_prices[symbol]["ask"] = ask_price
                    print(f"HTX | {symbol} | Bid: {bid_price} | Ask: {ask_price}")

        except Exception as e:
            print(f"❌ Ошибка обработки данных HTX: {e}")

    # Обработка ошибок
    def on_error(self, ws, error):
        print(f"❌ Ошибка WebSocket HTX: {error}")

    # Закрытие соединения
    def on_close(self, ws, close_status_code, close_msg):
        print("❌ WebSocket HTX закрыт")

    # Запуск WebSocket с автоматическим восстановлением
    def start(self):
        while True:
            try:
                self.ws = websocket.WebSocketApp(
                    HTX_WS_URL,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                )
                self.ws.run_forever()
            except Exception as e:
                print(f"❌ Ошибка WebSocket HTX (перезапуск): {e}")
            time.sleep(5)  # Ждём перед повторным подключением


# Запуск в отдельном потоке
def run_htx_websocket():
    htx_ws = HTXWebSocket()  # Создаём объект WebSocket
    htx_ws.start()  # Запускаем


if __name__ == '__main__':
    htx_thread = threading.Thread(target=run_htx_websocket, daemon=True)
    htx_thread.start()

    # Поддерживаем основной поток активным
    while True:
        time.sleep(1)
