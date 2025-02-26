import time
import threading
import statistics
import logging
from test_bybit import BybitWebSocket  # Импортируем класс BybitWebSocket из файла bybit.py

# ----------------- Настройка логирования сделок -----------------
trade_logger = logging.getLogger("trade_logger")
trade_logger.setLevel(logging.INFO)
console_output = logging.StreamHandler()
trade_handler = logging.FileHandler("logs/trading_log.txt")
trade_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
trade_logger.addHandler(trade_handler)
trade_logger.addHandler(console_output)

# Добавляем логгер для отслеживания тренда
trend_logger = logging.getLogger("trend_logger")
trend_logger.setLevel(logging.INFO)
trend_handler = logging.FileHandler("logs/trend_log.txt")
trend_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
trend_logger.addHandler(trend_handler)
trend_logger.addHandler(console_output)

# ----------------- Глобальные переменные -----------------
# Начальный баланс (общий кошелёк)
wallet = 1000.0

# Глобальный словарь цен – данные обновляются модулем bybit.py (реальные данные)
prices = {
    "BTCUSDT": {},
    "ETHUSDT": {}
}

# ----------------- Параметры стратегии -----------------
SHORT_WINDOW = 5  # короткое окно для SMA (секунд)
LONG_WINDOW = 15  # длинное окно для SMA (секунд)
TREND_THRESHOLD = 0.0005  # 0.05% разница между SMA для входа
PROFIT_TARGET = 0.005  # 0.5% целевая прибыль для выхода
REVERSAL_PROFIT_THRESHOLD = 0.0025  # 0.25% для выхода при развороте тренда (ниже основного порога)
STOP_LOSS = 0.01  # 1% максимальные потери (стоп-лосс)
MIN_INTERVAL = 10  # минимум 10 секунд между сделками
SAMPLE_INTERVAL = 0.5  # обновление каждые 0.5 секунды
TRADING_FEE = 0.001  # комиссия 0.1% за сделку (на вход и выход)
MIN_LIQUIDITY = 10000  # порог ликвидности
TREND_REVERSAL_TIME = 5  # время для определения разворота тренда (секунды)


# ----------------- Торговая стратегия -----------------
def trading_strategy(prices):
    global wallet
    # Хранение истории цен (mid-цены) для каждого символа
    price_history = {symbol: [] for symbol in prices.keys()}

    # Информация о позициях
    positions = {symbol: None for symbol in prices.keys()}  # None, "long" или "short"
    entry_prices = {symbol: None for symbol in prices.keys()}  # Цена входа
    trade_amount = {symbol: None for symbol in prices.keys()}  # Сумма сделки
    last_trade_time = {symbol: 0 for symbol in prices.keys()}  # Время последней сделки

    # Для отслеживания разворота тренда
    trend_direction = {symbol: None for symbol in prices.keys()}  # "up", "down" или None
    trend_start_time = {symbol: None for symbol in prices.keys()}  # Время начала разворота
    last_prices = {symbol: None for symbol in prices.keys()}  # Предыдущая цена
    trend_duration = {symbol: 0 for symbol in prices.keys()}  # Длительность текущего тренда в секундах

    while True:
        now = time.time()

        for symbol in prices.keys():
            bybit_data = prices.get(symbol, {}).get("bybit", {})
            bid = bybit_data.get("bid")
            ask = bybit_data.get("ask")

            if bid is None or ask is None:
                continue

            mid_price = (bid + ask) / 2.0

            # Обновляем историю цен
            price_history[symbol].append(mid_price)
            if len(price_history[symbol]) > LONG_WINDOW:
                price_history[symbol].pop(0)

            # Пропускаем, если недостаточно исторических данных
            if len(price_history[symbol]) < LONG_WINDOW:
                continue

            # Вычисляем SMA
            sma_short = statistics.mean(price_history[symbol][-SHORT_WINDOW:])
            sma_long = statistics.mean(price_history[symbol])

            # Отслеживание разворота тренда
            if last_prices[symbol] is not None and positions[symbol] is not None:
                current_direction = "up" if mid_price > last_prices[symbol] else "down"

                # Логируем изменение цены и направление
                price_change = ((mid_price - last_prices[symbol]) / last_prices[symbol]) * 100
                trend_logger.info(
                    f"{symbol}: Текущая цена: {mid_price:.6f}, Изменение: {price_change:.4f}%, Направление: {current_direction}")

                # Проверяем разворот тренда в зависимости от типа позиции
                if positions[symbol] == "long":
                    # Расчет текущей прибыли/убытка для LONG позиции
                    profit_percent = (mid_price - entry_prices[symbol]) / entry_prices[symbol]

                    # Проверяем СТОП-ЛОСС для LONG позиции
                    if profit_percent <= -STOP_LOSS:
                        new_balance = trade_amount[symbol] * (1 + profit_percent - 2 * TRADING_FEE)
                        trade_logger.info(
                            f"ПРОДАЖА (СТОП-ЛОСС): {symbol} по цене {mid_price:.6f}, убыток {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                        print(
                            f"ПРОДАЖА (СТОП-ЛОСС): {symbol} по цене {mid_price:.6f}, убыток {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                        wallet = new_balance
                        positions[symbol] = None
                        entry_prices[symbol] = None
                        trade_amount[symbol] = None
                        trend_direction[symbol] = None
                        trend_start_time[symbol] = None
                        last_trade_time[symbol] = now
                        continue

                    # Для LONG: опасный разворот - это падение цены
                    if current_direction == "down":
                        if trend_direction[symbol] != "down":
                            # Новый разворот тренда вниз
                            trend_direction[symbol] = "down"
                            trend_start_time[symbol] = now
                            trend_duration[symbol] = 0
                            trend_logger.info(
                                f"{symbol}: Обнаружен новый НИСХОДЯЩИЙ тренд при LONG позиции. Цена: {mid_price:.6f}")
                        else:
                            # Продолжаем отслеживать НИСХОДЯЩИЙ тренд
                            trend_duration[symbol] = now - trend_start_time[symbol]
                            trend_logger.info(
                                f"{symbol}: НИСХОДЯЩИЙ тренд продолжается {trend_duration[symbol]:.1f} сек. Цена: {mid_price:.6f}")

                            if trend_duration[symbol] >= TREND_REVERSAL_TIME:
                                # Разворот продолжается TREND_REVERSAL_TIME секунд
                                # Проверяем, достаточна ли прибыль для выхода
                                if profit_percent >= REVERSAL_PROFIT_THRESHOLD:  # Используем сниженный порог
                                    new_balance = trade_amount[symbol] * (1 + profit_percent - 2 * TRADING_FEE)
                                    trade_logger.info(
                                        f"ПРОДАЖА (РАЗВОРОТ): {symbol} по цене {mid_price:.6f}, прибыль {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                                    print(
                                        f"ПРОДАЖА (РАЗВОРОТ): {symbol} по цене {mid_price:.6f}, прибыль {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                                    wallet = new_balance
                                    positions[symbol] = None
                                    entry_prices[symbol] = None
                                    trade_amount[symbol] = None
                                    trend_direction[symbol] = None
                                    trend_start_time[symbol] = None
                                    last_trade_time[symbol] = now
                                else:
                                    trend_logger.info(
                                        f"{symbol}: Разворот тренда обнаружен, но прибыль ({profit_percent * 100:.2f}%) недостаточна для выхода (порог: {REVERSAL_PROFIT_THRESHOLD * 100:.2f}%)")
                    else:
                        # Тренд идет в нужном направлении, сбрасываем отслеживание разворота
                        if trend_direction[symbol] == "down":
                            trend_logger.info(f"{symbol}: НИСХОДЯЩИЙ тренд прерван. Цена: {mid_price:.6f}")
                        trend_direction[symbol] = None
                        trend_start_time[symbol] = None
                        trend_duration[symbol] = 0

                elif positions[symbol] == "short":
                    # Расчет текущей прибыли/убытка для SHORT позиции
                    profit_percent = (entry_prices[symbol] - mid_price) / entry_prices[symbol]

                    # Проверяем СТОП-ЛОСС для SHORT позиции
                    if profit_percent <= -STOP_LOSS:
                        new_balance = trade_amount[symbol] * (1 + profit_percent - 2 * TRADING_FEE)
                        trade_logger.info(
                            f"ПОКУПКА (СТОП-ЛОСС): {symbol} по цене {mid_price:.6f}, убыток {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                        print(
                            f"ПОКУПКА (СТОП-ЛОСС): {symbol} по цене {mid_price:.6f}, убыток {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                        wallet = new_balance
                        positions[symbol] = None
                        entry_prices[symbol] = None
                        trade_amount[symbol] = None
                        trend_direction[symbol] = None
                        trend_start_time[symbol] = None
                        last_trade_time[symbol] = now
                        continue

                    # Для SHORT: опасный разворот - это рост цены
                    if current_direction == "up":
                        if trend_direction[symbol] != "up":
                            # Новый разворот тренда вверх
                            trend_direction[symbol] = "up"
                            trend_start_time[symbol] = now
                            trend_duration[symbol] = 0
                            trend_logger.info(
                                f"{symbol}: Обнаружен новый ВОСХОДЯЩИЙ тренд при SHORT позиции. Цена: {mid_price:.6f}")
                        else:
                            # Продолжаем отслеживать ВОСХОДЯЩИЙ тренд
                            trend_duration[symbol] = now - trend_start_time[symbol]
                            trend_logger.info(
                                f"{symbol}: ВОСХОДЯЩИЙ тренд продолжается {trend_duration[symbol]:.1f} сек. Цена: {mid_price:.6f}")

                            if trend_duration[symbol] >= TREND_REVERSAL_TIME:
                                # Разворот продолжается TREND_REVERSAL_TIME секунд
                                # Проверяем, достаточна ли прибыль для выхода
                                if profit_percent >= REVERSAL_PROFIT_THRESHOLD:  # Используем сниженный порог
                                    new_balance = trade_amount[symbol] * (1 + profit_percent - 2 * TRADING_FEE)
                                    trade_logger.info(
                                        f"ПОКУПКА (РАЗВОРОТ): {symbol} по цене {mid_price:.6f}, прибыль {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                                    print(
                                        f"ПОКУПКА (РАЗВОРОТ): {symbol} по цене {mid_price:.6f}, прибыль {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                                    wallet = new_balance
                                    positions[symbol] = None
                                    entry_prices[symbol] = None
                                    trade_amount[symbol] = None
                                    trend_direction[symbol] = None
                                    trend_start_time[symbol] = None
                                    last_trade_time[symbol] = now
                                else:
                                    trend_logger.info(
                                        f"{symbol}: Разворот тренда обнаружен, но прибыль ({profit_percent * 100:.2f}%) недостаточна для выхода (порог: {REVERSAL_PROFIT_THRESHOLD * 100:.2f}%)")
                    else:
                        # Тренд идет в нужном направлении, сбрасываем отслеживание разворота
                        if trend_direction[symbol] == "up":
                            trend_logger.info(f"{symbol}: ВОСХОДЯЩИЙ тренд прерван. Цена: {mid_price:.6f}")
                        trend_direction[symbol] = None
                        trend_start_time[symbol] = None
                        trend_duration[symbol] = 0

            # Сохраняем текущую цену для следующей итерации
            last_prices[symbol] = mid_price

            # Проверяем, можно ли открыть новую позицию
            if all(pos is None for pos in positions.values()) and wallet > 0 and (
                    now - last_trade_time[symbol] > MIN_INTERVAL):
                trade_logger.info(f'Wallet: {wallet}')
                # Вход LONG: если краткосрочное SMA значительно выше длинного SMA
                if sma_short > sma_long * (1 + TREND_THRESHOLD):
                    positions[symbol] = "long"
                    entry_prices[symbol] = mid_price
                    trade_amount[symbol] = wallet  # используем весь кошелёк
                    last_trade_time[symbol] = now
                    trade_logger.info(f"{symbol}: ВХОД LONG по цене {mid_price:.6f}. Баланс: {wallet:.2f}")
                    print(f"{symbol}: ВХОД LONG по цене {mid_price:.6f}. Баланс: {wallet:.2f}")
                    wallet = 0  # весь баланс инвестирован

                # Вход SHORT: если краткосрочное SMA значительно ниже длинного SMA
                elif sma_short < sma_long * (1 - TREND_THRESHOLD):
                    positions[symbol] = "short"
                    entry_prices[symbol] = mid_price
                    trade_amount[symbol] = wallet  # используем весь кошелёк
                    last_trade_time[symbol] = now
                    trade_logger.info(f"{symbol}: ВХОД SHORT по цене {mid_price:.6f}. Баланс: {wallet:.2f}")
                    print(f"{symbol}: ВХОД SHORT по цене {mid_price:.6f}. Баланс: {wallet:.2f}")
                    wallet = 0

            # Если позиция открыта, проверяем условия для целевой прибыли
            elif positions[symbol] == "long":
                # Проверка на достижение целевой прибыли (PROFIT_TARGET = 0.5%)
                profit_percent = (mid_price - entry_prices[symbol]) / entry_prices[symbol]

                if profit_percent >= PROFIT_TARGET:
                    net_profit = profit_percent - 2 * TRADING_FEE
                    new_balance = trade_amount[symbol] * (1 + net_profit)
                    trade_logger.info(
                        f"ПРОДАЖА (ЦЕЛЬ): {symbol} по цене {mid_price:.6f}, прибыль {net_profit * 100:.2f}%, новый баланс {new_balance:.2f}")
                    print(
                        f"ПРОДАЖА (ЦЕЛЬ): {symbol} по цене {mid_price:.6f}, прибыль {net_profit * 100:.2f}%, новый баланс {new_balance:.2f}")
                    wallet = new_balance
                    positions[symbol] = None
                    entry_prices[symbol] = None
                    trade_amount[symbol] = None
                    trend_direction[symbol] = None
                    trend_start_time[symbol] = None
                    last_trade_time[symbol] = now

            elif positions[symbol] == "short":
                # Проверка на достижение целевой прибыли (PROFIT_TARGET = 0.5%)
                profit_percent = (entry_prices[symbol] - mid_price) / entry_prices[symbol]

                if profit_percent >= PROFIT_TARGET:
                    net_profit = profit_percent - 2 * TRADING_FEE
                    new_balance = trade_amount[symbol] * (1 + net_profit)
                    trade_logger.info(
                        f"ПОКУПКА (ЦЕЛЬ): {symbol} по цене {mid_price:.6f}, прибыль {net_profit * 100:.2f}%, новый баланс {new_balance:.2f}")
                    print(
                        f"ПОКУПКА (ЦЕЛЬ): {symbol} по цене {mid_price:.6f}, прибыль {net_profit * 100:.2f}%, новый баланс {new_balance:.2f}")
                    wallet = new_balance
                    positions[symbol] = None
                    entry_prices[symbol] = None
                    trade_amount[symbol] = None
                    trend_direction[symbol] = None
                    trend_start_time[symbol] = None
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
    try:
        while True:
            print(f'{prices}\n')
            print(f'Wallet: {wallet}\n')
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем.")