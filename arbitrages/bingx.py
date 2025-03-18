import json
import websocket
import gzip
import io
import threading
import time
from logs.log_settings import logger


BINGX_WS_URL = "wss://open-api-swap.bingx.com/swap-market"
PAIRS = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'XRP-USDT', 'DOGE-USDT', 'SUI-USDT', 'LTC-USDT', 'IP-USDT', 'ADA-USDT']
SUBSCRIPTIONS = [{"id": "bingx-depth", "reqType": "sub", "dataType": f"{pair}@depth5@500ms"} for pair in PAIRS]
bingx_prices = {
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


class BingXWebSocket:
    def __init__(self, prices):
        self.ws = None
        self.prices = prices
        self.reconnect = True

    def on_open(self, ws):
        logger.info("✅ Подключено к WebSocket BingX")
        for sub in SUBSCRIPTIONS:
            ws.send(json.dumps(sub))
            print("📡 Подписка отправлена:", sub)

    def decode_message(self, message):
        compressed_data = gzip.GzipFile(fileobj=io.BytesIO(message), mode="rb")
        decompressed_data = compressed_data.read()
        return decompressed_data.decode("utf-8")

    def on_message(self, ws, message):
        utf8_data = self.decode_message(message)
        data = json.loads(utf8_data)
        if "ping" in data:
            ws.send(json.dumps({"pong": data["ping"]}))

        if "data" in data and "bids" in data["data"] and "asks" in data["data"]:
            symbol = data["dataType"].split('@')[0].replace('-', '')
            bid_price = float(data["data"]["bids"][0][0])
            ask_price = float(data["data"]["asks"][0][0])
            if symbol in bingx_prices:
                self.prices[symbol]["bingx"] = {"bid": bid_price, "ask": ask_price}

    def on_error(self, ws, error):
        print(f"Ошибка WebSocket BingX: {error}")
        self.clear_prices()

    def on_close(self, ws, close_status_code, close_msg):
        if self.reconnect:
            logger.error(f"⚠️ WebSocket BingX закрыт")
            logger.info("🔄 Переподключение к WebSocket BingX через 5 сек...")
            time.sleep(5)
            self.start()

    def clear_prices(self):
        for symbol in self.prices:
            if "bingx" in self.prices[symbol]:
                del self.prices[symbol]["bingx"]

    def start(self):
        self.ws = websocket.WebSocketApp(
            BINGX_WS_URL,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close)
        self.ws.run_forever()


if __name__ == '__main__':
    def run_bingx_websocket():
        bingx_ws = BingXWebSocket(bingx_prices)
        bingx_ws.start()
    bingx_thread = threading.Thread(target=run_bingx_websocket, daemon=True)
    bingx_thread.start()
    while True:
        time.sleep(1)
