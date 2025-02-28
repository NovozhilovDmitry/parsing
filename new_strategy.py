import time
import threading
import statistics
import logging
import math
from test_bybit import BybitWebSocket  # Импортируем класс BybitWebSocket из файла bybit.py


trade_logger = logging.getLogger("trade_logger")
trade_logger.setLevel(logging.INFO)
console_output = logging.StreamHandler()
trade_handler = logging.FileHandler("logs/trading_log.txt")
trade_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
trade_logger.addHandler(trade_handler)
trade_logger.addHandler(console_output)


trend_logger = logging.getLogger("trend_logger")
trend_logger.setLevel(logging.INFO)
trend_handler = logging.FileHandler("logs/trend_log.txt")
trend_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
trend_logger.addHandler(trend_handler)
trend_logger.addHandler(console_output)

wallet = 1000.0

prices = {
    "BTCUSDT": {},
    "ETHUSDT": {}
}

SHORT_WINDOW = 30
LONG_WINDOW = 90
MICRO_WINDOW = 110
TREND_THRESHOLD = 0.001
PROFIT_TARGET = 0.003
REVERSAL_PROFIT_THRESHOLD = 0.0015
MICRO_PROFIT_THRESHOLD = 0.0015
STOP_LOSS = 0.003
TREND_REVERSAL_TIME = 6
MIN_INTERVAL = 5
SAMPLE_INTERVAL = 0.5
TRADING_FEE = 0.001
MIN_LIQUIDITY = 10000
PRICE_CHECK_WINDOW = 4
MAX_TIME_IN_POSITION = 300


def is_volatility_excessive(prices, window=10, threshold=0.02):
    if len(prices) < window:
        return False
    price_range = max(prices[-window:]) - min(prices[-window:])
    avg_price = statistics.mean(prices[-window:])
    return (price_range / avg_price) > threshold


def trading_strategy(prices):
    global wallet
    price_history = {symbol: [] for symbol in prices.keys()}
    micro_price_history = {symbol: [] for symbol in prices.keys()}
    positions = {symbol: None for symbol in prices.keys()}  # None, "long" или "short"
    entry_prices = {symbol: None for symbol in prices.keys()}  # Цена входа
    trade_amount = {symbol: None for symbol in prices.keys()}  # Сумма сделки
    last_trade_time = {symbol: 0 for symbol in prices.keys()}  # Время последней сделки
    entry_time = {symbol: None for symbol in prices.keys()}  # Время входа в позицию
    trend_direction = {symbol: None for symbol in prices.keys()}  # "up", "down" или None
    trend_start_time = {symbol: None for symbol in prices.keys()}  # Время начала разворота
    last_prices = {symbol: None for symbol in prices.keys()}  # Предыдущая цена
    trend_duration = {symbol: 0 for symbol in prices.keys()}  # Длительность текущего тренда в секундах
    micro_trend = {symbol: None for symbol in prices.keys()}  # "up", "down" или None
    micro_trend_duration = {symbol: 0 for symbol in prices.keys()}  # Количество последовательных цен в микротренде
    micro_trend_start_price = {symbol: None for symbol in prices.keys()}  # Начальная цена микротренда

    while True:
        now = time.time()

        for symbol in prices.keys():
            bybit_data = prices.get(symbol, {}).get("bybit", {})
            bid = bybit_data.get("bid")
            ask = bybit_data.get("ask")

            if bid is None or ask is None:
                continue

            mid_price = (bid + ask) / 2.0

            if mid_price <= 0 or math.isnan(mid_price):
                continue

            price_history[symbol].append(mid_price)
            if len(price_history[symbol]) > LONG_WINDOW:
                price_history[symbol].pop(0)

            micro_price_history[symbol].append(mid_price)
            if len(micro_price_history[symbol]) > MICRO_WINDOW:
                micro_price_history[symbol].pop(0)

            if len(price_history[symbol]) < LONG_WINDOW:
                continue

            if len(micro_price_history[symbol]) == MICRO_WINDOW and positions[symbol] is not None:
                current_micro_direction = None
                if all(micro_price_history[symbol][i] < micro_price_history[symbol][i + 1] for i in
                       range(MICRO_WINDOW - 1)):
                    current_micro_direction = "up"
                elif all(micro_price_history[symbol][i] > micro_price_history[symbol][i + 1] for i in
                         range(MICRO_WINDOW - 1)):
                    current_micro_direction = "down"

                if current_micro_direction is not None:
                    if positions[symbol] == "long" and current_micro_direction == "down":
                        profit_percent = (mid_price - entry_prices[symbol]) / entry_prices[symbol]
                        if profit_percent >= MICRO_PROFIT_THRESHOLD:
                            new_balance = trade_amount[symbol] * (1 + profit_percent - 2 * TRADING_FEE)
                            trade_logger.info(f"ПРОДАЖА (МИКРО-РАЗВОРОТ): {symbol} по цене {mid_price:.6f}, "
                                              f"прибыль {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                            print(f"ПРОДАЖА (МИКРО-РАЗВОРОТ): {symbol} по цене {mid_price:.6f}, "
                                  f"прибыль {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                            wallet = new_balance
                            positions[symbol] = None
                            entry_prices[symbol] = None
                            trade_amount[symbol] = None
                            trend_direction[symbol] = None
                            trend_start_time[symbol] = None
                            last_trade_time[symbol] = now
                            continue

                    elif positions[symbol] == "short" and current_micro_direction == "up":
                        profit_percent = (entry_prices[symbol] - mid_price) / entry_prices[symbol]
                        if profit_percent >= MICRO_PROFIT_THRESHOLD:
                            new_balance = trade_amount[symbol] * (1 + profit_percent - 2 * TRADING_FEE)
                            trade_logger.info(f"ПОКУПКА (МИКРО-РАЗВОРОТ): {symbol} по цене {mid_price:.6f}, "
                                              f"прибыль {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                            print(f"ПОКУПКА (МИКРО-РАЗВОРОТ): {symbol} по цене {mid_price:.6f}, "
                                  f"прибыль {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                            wallet = new_balance
                            positions[symbol] = None
                            entry_prices[symbol] = None
                            trade_amount[symbol] = None
                            trend_direction[symbol] = None
                            trend_start_time[symbol] = None
                            last_trade_time[symbol] = now
                            continue

            sma_short = statistics.mean(price_history[symbol][-SHORT_WINDOW:])
            sma_long = statistics.mean(price_history[symbol])

            sma_short_prev = statistics.mean(price_history[symbol][-SHORT_WINDOW - 1:-1]) if len(
                price_history[symbol]) > SHORT_WINDOW + 1 else sma_short
            sma_long_prev = statistics.mean(price_history[symbol][:-1]) if len(price_history[symbol]) > 1 else sma_long
            ma_trend = "up" if sma_short > sma_long and sma_short_prev <= sma_long_prev else "down" \
                if sma_short < sma_long and sma_short_prev >= sma_long_prev else None

            if positions[symbol] is not None and entry_time[symbol] is not None:
                time_in_position = now - entry_time[symbol]
                if time_in_position >= MAX_TIME_IN_POSITION:
                    if positions[symbol] == "long":
                        profit_percent = (mid_price - entry_prices[symbol]) / entry_prices[symbol]
                        new_balance = trade_amount[symbol] * (1 + profit_percent - 2 * TRADING_FEE)
                        trade_logger.info(f"ПРОДАЖА (МАКС ВРЕМЯ): {symbol} по цене {mid_price:.6f}, "
                                          f"результат {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                        print(f"ПРОДАЖА (МАКС ВРЕМЯ): {symbol} по цене {mid_price:.6f}, "
                              f"результат {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                        wallet = new_balance
                    elif positions[symbol] == "short":
                        profit_percent = (entry_prices[symbol] - mid_price) / entry_prices[symbol]
                        new_balance = trade_amount[symbol] * (1 + profit_percent - 2 * TRADING_FEE)
                        trade_logger.info(f"ПОКУПКА (МАКС ВРЕМЯ): {symbol} по цене {mid_price:.6f}, "
                                          f"результат {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                        print(f"ПОКУПКА (МАКС ВРЕМЯ): {symbol} по цене {mid_price:.6f}, "
                              f"результат {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                        wallet = new_balance

                    positions[symbol] = None
                    entry_prices[symbol] = None
                    trade_amount[symbol] = None
                    entry_time[symbol] = None
                    trend_direction[symbol] = None
                    trend_start_time[symbol] = None
                    last_trade_time[symbol] = now
                    continue

            if last_prices[symbol] is not None and positions[symbol] is not None:
                current_direction = "up" if mid_price > last_prices[symbol] else "down"

                price_change = ((mid_price - last_prices[symbol]) / last_prices[symbol]) * 100
                trend_logger.info(
                    f"{symbol}: Текущая цена: {mid_price:.6f}, Изменение: {price_change:.4f}%, Направление: {current_direction}")

                if positions[symbol] == "long":
                    profit_percent = (mid_price - entry_prices[symbol]) / entry_prices[symbol]

                    if profit_percent <= -STOP_LOSS:
                        new_balance = trade_amount[symbol] * (1 + profit_percent - 2 * TRADING_FEE)
                        trade_logger.info(f"ПРОДАЖА (СТОП-ЛОСС): {symbol} по цене {mid_price:.6f}, "
                                          f"убыток {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                        print(f"ПРОДАЖА (СТОП-ЛОСС): {symbol} по цене {mid_price:.6f}, "
                              f"убыток {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                        wallet = new_balance
                        positions[symbol] = None
                        entry_prices[symbol] = None
                        trade_amount[symbol] = None
                        entry_time[symbol] = None
                        trend_direction[symbol] = None
                        trend_start_time[symbol] = None
                        last_trade_time[symbol] = now
                        continue

                    if current_direction == "down":
                        if trend_direction[symbol] != "down":
                            trend_direction[symbol] = "down"
                            trend_start_time[symbol] = now
                            trend_duration[symbol] = 0
                            trend_logger.info(
                                f"{symbol}: Обнаружен новый НИСХОДЯЩИЙ тренд при LONG позиции. Цена: {mid_price:.6f}")
                        else:
                            trend_duration[symbol] = now - trend_start_time[symbol]
                            trend_logger.info(
                                f"{symbol}: НИСХОДЯЩИЙ тренд продолжается {trend_duration[symbol]:.1f} сек. Цена: {mid_price:.6f}")

                            if trend_duration[symbol] >= TREND_REVERSAL_TIME:
                                if profit_percent >= REVERSAL_PROFIT_THRESHOLD:  # Используем сниженный порог
                                    new_balance = trade_amount[symbol] * (1 + profit_percent - 2 * TRADING_FEE)
                                    trade_logger.info(f"ПРОДАЖА (РАЗВОРОТ): {symbol} по цене {mid_price:.6f}, "
                                                      f"прибыль {profit_percent * 100:.2f}%, "
                                                      f"новый баланс {new_balance:.2f}")
                                    print(f"ПРОДАЖА (РАЗВОРОТ): {symbol} по цене {mid_price:.6f}, "
                                          f"прибыль {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                                    wallet = new_balance
                                    positions[symbol] = None
                                    entry_prices[symbol] = None
                                    trade_amount[symbol] = None
                                    entry_time[symbol] = None
                                    trend_direction[symbol] = None
                                    trend_start_time[symbol] = None
                                    last_trade_time[symbol] = now
                                else:
                                    trend_logger.info(
                                        f"{symbol}: Разворот тренда обнаружен, но прибыль ({profit_percent * 100:.2f}%)"
                                        f" недостаточна для выхода (порог: {REVERSAL_PROFIT_THRESHOLD * 100:.2f}%)")
                    else:
                        if trend_direction[symbol] == "down":
                            trend_logger.info(f"{symbol}: НИСХОДЯЩИЙ тренд прерван. Цена: {mid_price:.6f}")
                        trend_direction[symbol] = None
                        trend_start_time[symbol] = None
                        trend_duration[symbol] = 0

                elif positions[symbol] == "short":
                    profit_percent = (entry_prices[symbol] - mid_price) / entry_prices[symbol]

                    # Проверяем СТОП-ЛОСС для SHORT позиции
                    if profit_percent <= -STOP_LOSS:
                        new_balance = trade_amount[symbol] * (1 + profit_percent - 2 * TRADING_FEE)
                        trade_logger.info(
                            f"ПОКУПКА (СТОП-ЛОСС): {symbol} по цене {mid_price:.6f}, "
                            f"убыток {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                        print(
                            f"ПОКУПКА (СТОП-ЛОСС): {symbol} по цене {mid_price:.6f}, "
                            f"убыток {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                        wallet = new_balance
                        positions[symbol] = None
                        entry_prices[symbol] = None
                        trade_amount[symbol] = None
                        entry_time[symbol] = None
                        trend_direction[symbol] = None
                        trend_start_time[symbol] = None
                        last_trade_time[symbol] = now
                        continue

                    if current_direction == "up":
                        if trend_direction[symbol] != "up":
                            trend_direction[symbol] = "up"
                            trend_start_time[symbol] = now
                            trend_duration[symbol] = 0
                            trend_logger.info(
                                f"{symbol}: Обнаружен новый ВОСХОДЯЩИЙ тренд при SHORT позиции. Цена: {mid_price:.6f}")
                        else:
                            trend_duration[symbol] = now - trend_start_time[symbol]
                            trend_logger.info(
                                f"{symbol}: ВОСХОДЯЩИЙ тренд продолжается {trend_duration[symbol]:.1f} сек. "
                                f"Цена: {mid_price:.6f}")

                            if trend_duration[symbol] >= TREND_REVERSAL_TIME:
                                if profit_percent >= REVERSAL_PROFIT_THRESHOLD:  # Используем сниженный порог
                                    new_balance = trade_amount[symbol] * (1 + profit_percent - 2 * TRADING_FEE)
                                    trade_logger.info(f"ПОКУПКА (РАЗВОРОТ): {symbol} по цене {mid_price:.6f}, "
                                                      f"прибыль {profit_percent * 100:.2f}%, "
                                                      f"новый баланс {new_balance:.2f}")
                                    print(f"ПОКУПКА (РАЗВОРОТ): {symbol} по цене {mid_price:.6f}, "
                                          f"прибыль {profit_percent * 100:.2f}%, новый баланс {new_balance:.2f}")
                                    wallet = new_balance
                                    positions[symbol] = None
                                    entry_prices[symbol] = None
                                    trade_amount[symbol] = None
                                    entry_time[symbol] = None
                                    trend_direction[symbol] = None
                                    trend_start_time[symbol] = None
                                    last_trade_time[symbol] = now
                                else:
                                    trend_logger.info(
                                        f"{symbol}: Разворот тренда обнаружен, но прибыль ({profit_percent * 100:.2f}%) недостаточна для выхода (порог: {REVERSAL_PROFIT_THRESHOLD * 100:.2f}%)")
                    else:
                        if trend_direction[symbol] == "up":
                            trend_logger.info(f"{symbol}: ВОСХОДЯЩИЙ тренд прерван. Цена: {mid_price:.6f}")
                        trend_direction[symbol] = None
                        trend_start_time[symbol] = None
                        trend_duration[symbol] = 0

            last_prices[symbol] = mid_price

            if all(pos is None for pos in positions.values()) and wallet > 0 and (
                    now - last_trade_time[symbol] > MIN_INTERVAL):
                if is_volatility_excessive(price_history[symbol]):
                    trend_logger.info(f"{symbol}: Обнаружена высокая волатильность, сделка пропущена")
                    continue

                bid_volume = sum([level[1] for level in bybit_data.get("bids", [])[:5]])
                ask_volume = sum([level[1] for level in bybit_data.get("asks", [])[:5]])
                if min(bid_volume, ask_volume) < MIN_LIQUIDITY:
                    trend_logger.info(f"{symbol}: Недостаточная ликвидность, сделка пропущена")
                    continue

                trade_logger.info(f'Wallet: {wallet}')
                if sma_short > sma_long * (1 + TREND_THRESHOLD):
                    positions[symbol] = "long"
                    entry_prices[symbol] = mid_price
                    entry_time[symbol] = now
                    trade_amount[symbol] = wallet * 0.2  # используем 50% кошелька
                    wallet -= trade_amount[symbol]  # оставляем остаток в кошельке
                    last_trade_time[symbol] = now
                    trade_logger.info(f"{symbol}: ВХОД LONG по цене {mid_price:.6f}. Баланс: {wallet:.2f}")
                    print(f"{symbol}: ВХОД LONG по цене {mid_price:.6f}. Баланс: {wallet:.2f}")

                elif sma_short < sma_long * (1 - TREND_THRESHOLD):
                    positions[symbol] = "short"
                    entry_prices[symbol] = mid_price
                    entry_time[symbol] = now
                    trade_amount[symbol] = wallet * 0.2  # используем 50% кошелька
                    wallet -= trade_amount[symbol]  # оставляем остаток в кошельке
                    last_trade_time[symbol] = now
                    trade_logger.info(f"{symbol}: ВХОД SHORT по цене {mid_price:.6f}. Баланс: {wallet:.2f}")
                    print(f"{symbol}: ВХОД SHORT по цене {mid_price:.6f}. Баланс: {wallet:.2f}")

            elif positions[symbol] == "long":
                profit_percent = (mid_price - entry_prices[symbol]) / entry_prices[symbol]

                if profit_percent >= PROFIT_TARGET:
                    net_profit = profit_percent - 2 * TRADING_FEE
                    new_balance = trade_amount[symbol] * (1 + net_profit)
                    trade_logger.info(f"ПРОДАЖА (ЦЕЛЬ): {symbol} по цене {mid_price:.6f}, "
                                      f"прибыль {net_profit * 100:.2f}%, новый баланс {new_balance:.2f}")
                    print(f"ПРОДАЖА (ЦЕЛЬ): {symbol} по цене {mid_price:.6f}, "
                          f"прибыль {net_profit * 100:.2f}%, новый баланс {new_balance:.2f}")
                    wallet = new_balance
                    positions[symbol] = None
                    entry_prices[symbol] = None
                    trade_amount[symbol] = None
                    entry_time[symbol] = None
                    trend_direction[symbol] = None
                    trend_start_time[symbol] = None
                    last_trade_time[symbol] = now

            elif positions[symbol] == "short":
                profit_percent = (entry_prices[symbol] - mid_price) / entry_prices[symbol]

                if profit_percent >= PROFIT_TARGET:
                    net_profit = profit_percent - 2 * TRADING_FEE
                    new_balance = trade_amount[symbol] * (1 + net_profit)
                    trade_logger.info(f"ПОКУПКА (ЦЕЛЬ): {symbol} по цене {mid_price:.6f}, "
                                      f"прибыль {net_profit * 100:.2f}%, новый баланс {new_balance:.2f}")
                    print(f"ПОКУПКА (ЦЕЛЬ): {symbol} по цене {mid_price:.6f}, "
                          f"прибыль {net_profit * 100:.2f}%, новый баланс {new_balance:.2f}")
                    wallet = new_balance
                    positions[symbol] = None
                    entry_prices[symbol] = None
                    trade_amount[symbol] = None
                    entry_time[symbol] = None
                    trend_direction[symbol] = None
                    trend_start_time[symbol] = None
                    last_trade_time[symbol] = now

        time.sleep(SAMPLE_INTERVAL)


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


if __name__ == "__main__":
    bybit_thread = threading.Thread(target=run_bybit, daemon=True)
    bybit_thread.start()

    strategy_thread = threading.Thread(target=trading_strategy, args=(prices,), daemon=True)
    strategy_thread.start()

    try:
        while True:
            print(f'{prices}\n')
            print(f'Wallet: {wallet}\n')
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем.")
        print('Здесь будет повешена продажа существующих ордеров и выход в USDT')
