import threading
import time
from bingx import BingXWebSocket
from bybit import BybitWebSocket
from htx import HTXWebSocket
from okx import OKXWebSocket

# Функции для запуска WebSocket
def run_bingx():
    print("🔹 Запускаем BingX WebSocket")
    bingx_ws = BingXWebSocket()
    bingx_ws.start()

def run_bybit():
    print("🔹 Запускаем Bybit WebSocket")
    bybit_ws = BybitWebSocket()
    bybit_ws.start()

def run_htx():
    print("🔹 Запускаем HTX WebSocket")
    htx_ws = HTXWebSocket()
    htx_ws.start()

def run_okx():
    print("🔹 Запускаем OKX WebSocket")
    okx_ws = OKXWebSocket()
    okx_ws.start()

# Создаем и запускаем потоки
threads = [
    threading.Thread(target=run_bingx, daemon=True),
    threading.Thread(target=run_bybit, daemon=True),
    threading.Thread(target=run_htx, daemon=True),
    threading.Thread(target=run_okx, daemon=True),
]

for thread in threads:
    thread.start()

# Проверяем активность потоков
while True:
    print(f"🎯 Активные потоки: {threading.active_count()}")
    time.sleep(5)
