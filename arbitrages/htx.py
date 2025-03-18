import json
import websocket
import threading
import time
import gzip
from functions.log_settings import logger


HTX_WS_URL = "wss://api.huobi.pro/ws"
PAIRS = ['btcusdt', 'ethusdt', 'solusdt', 'xrpusdt', 'dogeusdt', 'suiusdt', 'ltcusdt', 'tonusdt', 'adausdt',
         'ipusdt']
SUBSCRIPTIONS = [{"sub": f"market.{pair}.depth.step0", "id": pair} for pair in PAIRS]
htx_prices = {
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


class HTXWebSocket:
    def __init__(self, prices):
        self.ws = None
        self.prices = prices
        self.reconnect = True

    def on_open(self, ws):
        logger.info("Подключено к WebSocket HTX")
        for sub in SUBSCRIPTIONS:
            ws.send(json.dumps(sub))
            print("Подписка отправлена:", sub)

    def decode_message(self, message):
        return gzip.decompress(message).decode("utf-8")

    def on_message(self, ws, message):
        try:
            utf8_data = self.decode_message(message)
            data = json.loads(utf8_data)

            if "ping" in data:
                ws.send(json.dumps({"pong": data["ping"]}))

            if "tick" in data and "bids" in data["tick"] and "asks" in data["tick"]:
                symbol = data["ch"].split(".")[1].upper()
                bid_price = float(data["tick"]["bids"][0][0])
                ask_price = float(data["tick"]["asks"][0][0])
                if symbol in htx_prices:
                    self.prices[symbol]["htx"] = {"bid": bid_price, "ask": ask_price}

        except Exception as e:
            print(f"Ошибка обработки данных HTX: {e}")

    def on_error(self, ws, error):
        print(f"Ошибка WebSocket HTX: {error}")
        self.clear_prices()

    def on_close(self, ws, close_status_code, close_msg):
        if self.reconnect:
            logger.error(f"WebSocket HTX закрыт")
            logger.info("Переподключение к WebSocket HTX через 5 сек...")
            time.sleep(5)
            self.start()

    def clear_prices(self):
        for symbol in self.prices:
            if "htx" in self.prices[symbol]:
                del self.prices[symbol]["htx"]

    def start(self):
        while True:
            try:
                self.ws = websocket.WebSocketApp(
                    HTX_WS_URL,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close)
                self.ws.run_forever()
            except Exception as e:
                print(f"Ошибка WebSocket HTX (перезапуск): {e}")
            time.sleep(5)


if __name__ == '__main__':
    def run_htx_websocket():
        htx_ws = HTXWebSocket(htx_prices)
        htx_ws.start()
    htx_thread = threading.Thread(target=run_htx_websocket, daemon=True)
    htx_thread.start()
    while True:
        time.sleep(1)
