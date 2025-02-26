import time
import threading
import statistics
import logging
from test_bybit import BybitWebSocket  # Реальные данные от Bybit

# ----------------- Настройка логирования сделок -----------------
trade_logger = logging.getLogger("trade_logger")
trade_logger.setLevel(logging.INFO)
console_output = logging.StreamHandler()
trade_handler = logging.FileHandler("logs/trading_log.txt")
trade_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
trade_logger.addHandler(trade_handler)
trade_logger.addHandler(console_output)

# ----------------- Глобальные переменные -----------------
# Начальный баланс (общий кошелёк)
wallet = 1000.0

# Глобальный словарь цен – данные обновляются модулем bybit.py (реальные данные)
prices = {
    "BTCUSDT": {},  # обновляется prices["BTCUSDT"]["bybit"]
    "ETHUSDT": {},  # обновляется prices["ETHUSDT"]["bybit"]
}

# ----------------- Параметры стратегии -----------------
SHORT_WINDOW = 5  # короткое окно для SMA (секунд)
LONG_WINDOW = 15  # длинное окно для SMA (секунд)
TREND_THRESHOLD = 0.0005  # 0.05% разница между SMA для входа
PROFIT_TARGET = 0.001  # 0.1% целевая чистая прибыль для выхода
MIN_INTERVAL = 10  # минимум 20 секунд между сделками
SAMPLE_INTERVAL = 1  # обновление каждую секунду
TRADING_FEE = 0.001  # комиссия 0.1% за сделку (на вход и выход)
MIN_LIQUIDITY = 10000  # порог ликвидности


# ----------------- Торговая стратегия -----------------
def trading_strategy(prices):
    global wallet
    # Хранение истории цен (mid-цены) для каждого символа (используем данные с Bybit)
    price_history = {
        "BTCUSDT": [],
        "ETHUSDT": []
    }
    # Текущее состояние позиции: None, "long" или "short"
    positions = {
        "BTCUSDT": None,
        "ETHUSDT": None
    }
    # Цена входа для расчёта прибыли
    entry_prices = {
        "BTCUSDT": None,
        "ETHUSDT": None
    }
    # Сумма, использованная при открытии сделки (чтобы потом пересчитать баланс)
    trade_amount = {
        "BTCUSDT": None,
        "ETHUSDT": None
    }
    # Время последней сделки для каждого символа
    last_trade_time = {
        "BTCUSDT": 0,
        "ETHUSDT": 0
    }

    while True:
        now = time.time()
        for symbol in ["BTCUSDT", "ETHUSDT"]:
            bybit_data = prices.get(symbol, {}).get("bybit", {})
            bid = bybit_data.get("bid")
            ask = bybit_data.get("ask")
            liquidity = bybit_data.get("liquidity", 1e6)
            if bid is None or ask is None or liquidity < MIN_LIQUIDITY:
                continue

            mid_price = (bid + ask) / 2.0

            # Обновляем историю цен для символа
            price_history[symbol].append(mid_price)
            if len(price_history[symbol]) > LONG_WINDOW:
                price_history[symbol].pop(0)

            if len(price_history[symbol]) < LONG_WINDOW:
                continue

            # Вычисляем SMA
            sma_short = statistics.mean(price_history[symbol][-SHORT_WINDOW:])
            sma_long = statistics.mean(price_history[symbol])
            print(f"{symbol}: mid={mid_price:.2f}, SMA_short={sma_short:.2f}, SMA_long={sma_long:.2f}")

            # Проверяем, что ни для одного символа нет открытой сделки (используем весь кошелёк)
            if all(pos is None for pos in positions.values()) and wallet > 0 and (
                    now - last_trade_time[symbol] > MIN_INTERVAL):
                trade_logger.info(f'Wallet: {wallet}')
                # Вход LONG: если краткосрочное SMA значительно выше длинного SMA
                if sma_short > sma_long * (1 + TREND_THRESHOLD):
                    positions[symbol] = "long"
                    entry_prices[symbol] = mid_price
                    trade_amount[symbol] = wallet  # используем весь кошелёк
                    last_trade_time[symbol] = now
                    trade_logger.info(f"{symbol}: ВХОД LONG по цене {mid_price:.2f}. Баланс: {wallet:.2f}")
                    print(f"{symbol}: ВХОД LONG по цене {mid_price:.2f}. Баланс: {wallet:.2f}")
                    wallet = 0  # весь баланс инвестирован
                # Вход SHORT: если краткосрочное SMA значительно ниже длинного SMA
                elif sma_short < sma_long * (1 - TREND_THRESHOLD):
                    positions[symbol] = "short"
                    entry_prices[symbol] = mid_price
                    trade_amount[symbol] = wallet  # используем весь кошелёк
                    last_trade_time[symbol] = now
                    trade_logger.info(f"{symbol}: ВХОД SHORT по цене {mid_price:.2f}. Баланс: {wallet:.2f}")
                    print(f"{symbol}: ВХОД SHORT по цене {mid_price:.2f}. Баланс: {wallet:.2f}")
                    wallet = 0
            else:
                # Если позиция уже открыта для данного символа, проверяем условия выхода
                if positions[symbol] == "long":
                    # Для LONG: прибыль = (текущая цена - цена входа) / цена входа
                    gross_profit = (mid_price - entry_prices[symbol]) / entry_prices[symbol]
                    net_profit = gross_profit - 2 * TRADING_FEE  # вычитаем комиссию
                    if net_profit >= PROFIT_TARGET and sma_short < sma_long:
                        new_balance = trade_amount[symbol] * (1 + net_profit)
                        print(
                            f"{symbol}: ВЫХОД LONG по цене {mid_price:.2f}, прибыль {net_profit * 100:.2f}%, новый баланс {new_balance:.2f}")
                        trade_logger.info(
                            f"купил токен {symbol} по цене {entry_prices[symbol]:.2f}. Продал токен {symbol} по цене {mid_price:.2f}. Прибыль {net_profit * 100:.2f}%. Новый баланс {new_balance:.2f}")
                        wallet = new_balance
                        positions[symbol] = None
                        entry_prices[symbol] = None
                        trade_amount[symbol] = None
                        last_trade_time[symbol] = now
                elif positions[symbol] == "short":
                    # Для SHORT: прибыль = (цена входа - текущая цена) / цена входа
                    gross_profit = (entry_prices[symbol] - mid_price) / entry_prices[symbol]
                    net_profit = gross_profit - 2 * TRADING_FEE
                    if net_profit >= PROFIT_TARGET and sma_short > sma_long:
                        new_balance = trade_amount[symbol] * (1 + net_profit)
                        print(
                            f"{symbol}: ВЫХОД SHORT по цене {mid_price:.2f}, прибыль {net_profit * 100:.2f}%, новый баланс {new_balance:.2f}")
                        trade_logger.info(
                            f"продал токен {symbol} по цене {entry_prices[symbol]:.2f}. Купил токен {symbol} по цене {mid_price:.2f}. Прибыль {net_profit * 100:.2f}%. Новый баланс {new_balance:.2f}")
                        wallet = new_balance
                        positions[symbol] = None
                        entry_prices[symbol] = None
                        trade_amount[symbol] = None
                        last_trade_time[symbol] = now

        time.sleep(SAMPLE_INTERVAL)


# ----------------- Функция запуска WebSocket Bybit (реальные данные) -----------------
def run_bybit():
    while True:
        try:
            print("🔹 Подключение к WebSocket Bybit...")
            trade_logger.info('Подключение к WebSocket Bybit...')
            ws_instance = BybitWebSocket(prices)
            ws_instance.start()
        except Exception as e:
            trade_logger.error(f'Ошибка WebSocket Bybit, повторное подключение через 5 секунд... {e}')
            print("⚠️ Ошибка WebSocket Bybit, повторное подключение через 5 секунд...", e)
            time.sleep(5)


# ----------------- Запуск потоков -----------------
if __name__ == "__main__":
    # Запускаем реальный WebSocket Bybit в отдельном потоке
    bybit_thread = threading.Thread(target=run_bybit, daemon=True)
    bybit_thread.start()

    # Запускаем торговую стратегию в отдельном потоке
    strategy_thread = threading.Thread(target=trading_strategy, args=(prices,), daemon=True)
    strategy_thread.start()

    # Основной поток остаётся активным
    while True:
        print(f'Wallet: {wallet}\n')
        time.sleep(1)
