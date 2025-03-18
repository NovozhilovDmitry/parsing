import json
import websocket
import threading
import time
from functions.log_settings import logger


OKX_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"
PAIRS = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'XRP-USDT', 'DOGE-USDT', 'SUI-USDT', 'LTC-USDT', 'IP-USDT', 'ADA-USDT',
         'TON-USDT']
SUBSCRIPTIONS = [{"op": "subscribe", "args": [{"channel": "tickers", "instId": pair}]} for pair in PAIRS]
okx_prices = {
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


class OKXWebSocket:
    def __init__(self, prices):
        self.ws = None
        self.prices = prices
        self.reconnect = True

    def on_open(self, ws):
        logger.info("Подключено к WebSocket OKX")
        for sub in SUBSCRIPTIONS:
            ws.send(json.dumps(sub))
            print("Подписка отправлена:", sub)

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if "event" in data and data["event"] == "subscribe":
                print(f"Подписка успешна: {data}")
                return

            if "arg" in data and "data" in data:
                ticker_data = data["data"][0]
                symbol = data["arg"]["instId"].replace('-', '')
                bid_price = float(ticker_data["bidPx"])
                ask_price = float(ticker_data["askPx"])
                if symbol in okx_prices:
                    self.prices[symbol]["okx"] = {"bid": bid_price, "ask": ask_price}
        except Exception as e:
            print(f"Ошибка обработки данных OKX: {e}")

    def on_error(self, ws, error):
        print(f"Ошибка WebSocket OKX: {error}")
        self.clear_prices()

    def on_close(self, ws, close_status_code, close_msg):
        if self.reconnect:
            logger.error("WebSocket OKX закрыт")
            logger.info("Переподключение к WebSocket OKX через 5 сек...")
            time.sleep(5)
            self.start()

    def clear_prices(self):
        for symbol in self.prices:
            if "okx" in self.prices[symbol]:
                del self.prices[symbol]["okx"]

    def start(self):
        while True:
            try:
                self.ws = websocket.WebSocketApp(
                    OKX_WS_URL,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close)
                self.ws.run_forever()
            except Exception as e:
                print(f"Ошибка WebSocket OKX (перезапуск): {e}")
            time.sleep(5)


if __name__ == '__main__':
    def run_okx_websocket():
        okx_ws = OKXWebSocket(okx_prices)
        okx_ws.start()
    okx_thread = threading.Thread(target=run_okx_websocket, daemon=True)
    okx_thread.start()
    while True:
        time.sleep(1)
