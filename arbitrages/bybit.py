import json
import websocket
import threading
import time
from logs.log_settings import logger


BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/spot"
PAIRS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'SUIUSDT', 'LTCUSDT', 'IPUSDT', 'ADAUSDT', 'TONUSDT']
SUBSCRIPTIONS = {"op": "subscribe", "args": [f"orderbook.1.{pair}" for pair in PAIRS]}
bybit_prices = {
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


class BybitWebSocket:
    def __init__(self, prices):
        self.ws = None
        self.prices = prices
        self.reconnect = True

    def on_open(self, ws):
        logger.info("✅ Подключено к WebSocket Bybit")
        ws.send(json.dumps(SUBSCRIPTIONS))
        print("📡 Подписка отправлена:", SUBSCRIPTIONS)

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

                if bids and asks:
                    bid_price = float(bids[0][0])
                    ask_price = float(asks[0][0])

                    if symbol in bybit_prices:
                        self.prices[symbol]["bybit"] = {"bid": bid_price, "ask": ask_price}

        except Exception as e:
            print(f"❌ Ошибка обработки данных Bybit: {e}")

    def on_error(self, ws, error):
        print(f"❌ Ошибка WebSocket Bybit: {error}")
        self.clear_prices()

    def on_close(self, ws, close_status_code, close_msg):
        logger.warning(f'BYBIT WS: {ws}, Close_status_code: {close_status_code}, Close_msg: {close_msg}')
        if self.reconnect:
            logger.error(print("❌ WebSocket Bybit закрыт"))
            logger.info("🔄 Переподключение к WebSocket Bybit через 5 сек...")
            time.sleep(5)
            self.start()

    def clear_prices(self):
        for symbol in self.prices:
            if "bybit" in self.prices[symbol]:
                del self.prices[symbol]["bybit"]

    def start(self):
        while True:
            try:
                self.ws = websocket.WebSocketApp(
                    BYBIT_WS_URL,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close)
                self.ws.run_forever()
            except Exception as e:
                print(f"❌ Ошибка WebSocket Bybit (перезапуск): {e}")
            time.sleep(5)


if __name__ == '__main__':
    def run_bybit_websocket():
        bybit_ws = BybitWebSocket(bybit_prices)
        bybit_ws.start()
    bybit_thread = threading.Thread(target=run_bybit_websocket, daemon=True)
    bybit_thread.start()
    while True:
        print(bybit_prices)
        time.sleep(1)
