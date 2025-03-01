import time
import threading
from order_functions import (setup_logging, calculate_indicators, check_profit_target, check_entry_conditions,
                             get_market_data, check_micro_trend_exit, check_trend_reversal, check_stop_loss,
                             check_quick_exit)
from tst_bybit import BybitWebSocket


prices = {
    "BTCUSDT": {},
    "ETHUSDT": {}
}


class TradingConfig:
    INITIAL_WALLET = 1000.0
    SHORT_WINDOW = 30
    LONG_WINDOW = 90
    MICRO_WINDOW = 10
    TREND_THRESHOLD = 0.001
    PROFIT_TARGET = 0.003
    REVERSAL_PROFIT_THRESHOLD = 0.0015
    MICRO_PROFIT_THRESHOLD = 0.0015
    STOP_LOSS = 0.003
    TREND_REVERSAL_TIME = 6
    MIN_INTERVAL = 20
    SAMPLE_INTERVAL = 0.5
    MAX_TIME_IN_POSITION = 300
    TRADING_FEE = 0.001
    MIN_LIQUIDITY = 100
    PRICE_CHECK_WINDOW = 4
    POSITION_SIZE_PERCENT = 0.25


def trading_strategy(prices):
    """Main trading strategy function with state management"""
    trade_logger, trend_logger = setup_logging()

    config = TradingConfig()
    wallet = config.INITIAL_WALLET

    symbols = list(prices.keys())
    price_history = {symbol: [] for symbol in symbols}
    micro_price_history = {symbol: [] for symbol in symbols}
    positions = {symbol: None for symbol in symbols}
    entry_prices = {symbol: None for symbol in symbols}
    trade_amount = {symbol: None for symbol in symbols}
    last_trade_time = {symbol: 0 for symbol in symbols}
    entry_time = {symbol: None for symbol in symbols}
    trend_direction = {symbol: None for symbol in symbols}
    trend_start_time = {symbol: None for symbol in symbols}
    last_prices = {symbol: None for symbol in symbols}
    trend_duration = {symbol: 0 for symbol in symbols}

    while True:
        now = time.time()

        for symbol in symbols:
            bybit_data = prices.get(symbol, {}).get("bybit", {})
            bid, ask, mid_price, bid_volume, ask_volume = get_market_data(bybit_data)

            if mid_price is None:
                continue

            price_history[symbol].append(mid_price)
            if len(price_history[symbol]) > config.LONG_WINDOW:
                price_history[symbol].pop(0)

            micro_price_history[symbol].append(mid_price)
            if len(micro_price_history[symbol]) > config.MICRO_WINDOW:
                micro_price_history[symbol].pop(0)

            if len(price_history[symbol]) < config.LONG_WINDOW:
                continue

            sma_short, sma_long, sma_short_prev, sma_long_prev, ma_trend = calculate_indicators(
                price_history[symbol], config.SHORT_WINDOW, config.LONG_WINDOW
            )

            if positions[symbol] is not None:
                exit_triggered, new_balance = check_micro_trend_exit(
                    symbol, positions[symbol], micro_price_history[symbol], mid_price,
                    entry_prices[symbol], trade_amount[symbol], trade_logger, config
                )

                if exit_triggered:
                    wallet = new_balance
                    positions[symbol] = None
                    entry_prices[symbol] = None
                    trade_amount[symbol] = None
                    trend_direction[symbol] = None
                    trend_start_time[symbol] = None
                    last_trade_time[symbol] = now
                    continue

                if entry_time[symbol] is not None:
                    time_in_position = now - entry_time[symbol]
                    exit_triggered, new_balance = check_quick_exit(
                        symbol, positions[symbol], time_in_position, mid_price, entry_prices[symbol],
                        sma_short, sma_long, trade_amount[symbol], trade_logger, config
                    )

                    if exit_triggered:
                        wallet = new_balance
                        positions[symbol] = None
                        entry_prices[symbol] = None
                        trade_amount[symbol] = None
                        entry_time[symbol] = None
                        trend_direction[symbol] = None
                        trend_start_time[symbol] = None
                        last_trade_time[symbol] = now
                        continue

                if last_prices[symbol] is not None:
                    current_direction = "up" if mid_price > last_prices[symbol] else "down"
                    price_change = ((mid_price - last_prices[symbol]) / last_prices[symbol]) * 100
                    trend_logger.info(
                        f"{symbol}: Текущая цена: {mid_price:.6f}, Изменение: {price_change:.4f}%, "
                        f"Направление: {current_direction}")

                    exit_triggered, new_balance = check_stop_loss(
                        symbol, positions[symbol], mid_price, entry_prices[symbol],
                        trade_amount[symbol], trade_logger, config
                    )

                    if exit_triggered:
                        wallet = new_balance
                        positions[symbol] = None
                        entry_prices[symbol] = None
                        trade_amount[symbol] = None
                        entry_time[symbol] = None
                        trend_direction[symbol] = None
                        trend_start_time[symbol] = None
                        last_trade_time[symbol] = now
                        continue

                    exit_triggered, new_balance, new_trend_dir, new_trend_start, new_trend_duration, trend_changed = check_trend_reversal(
                        symbol, positions[symbol], current_direction, trend_direction[symbol],
                        trend_start_time[symbol], trend_duration[symbol], mid_price, entry_prices[symbol],
                        trade_amount[symbol], trend_logger, trade_logger, config, now
                    )

                    if trend_changed:
                        trend_direction[symbol] = new_trend_dir
                        trend_start_time[symbol] = new_trend_start
                        trend_duration[symbol] = new_trend_duration

                    if exit_triggered:
                        wallet = new_balance
                        positions[symbol] = None
                        entry_prices[symbol] = None
                        trade_amount[symbol] = None
                        entry_time[symbol] = None
                        trend_direction[symbol] = None
                        trend_start_time[symbol] = None
                        last_trade_time[symbol] = now
                        continue

                exit_triggered, new_balance = check_profit_target(
                    symbol, positions[symbol], mid_price, entry_prices[symbol],
                    trade_amount[symbol], trade_logger, config
                )

                if exit_triggered:
                    wallet = new_balance
                    positions[symbol] = None
                    entry_prices[symbol] = None
                    trade_amount[symbol] = None
                    entry_time[symbol] = None
                    trend_direction[symbol] = None
                    trend_start_time[symbol] = None
                    last_trade_time[symbol] = now
                    continue

            last_prices[symbol] = mid_price

            if all(pos is None for pos in positions.values()) and wallet > 0 and \
                    (now - last_trade_time[symbol] > config.MIN_INTERVAL):
                position_type, entry_price, position_amount = check_entry_conditions(
                    symbol, sma_short, sma_long, mid_price, wallet, bid_volume, ask_volume,
                    price_history[symbol], trend_logger, trade_logger, config
                )

                if position_type:
                    positions[symbol] = position_type
                    entry_prices[symbol] = entry_price
                    entry_time[symbol] = now
                    trade_amount[symbol] = position_amount
                    wallet -= position_amount
                    last_trade_time[symbol] = now

        time.sleep(config.SAMPLE_INTERVAL)


def run_bybit():
    """Manage Bybit WebSocket connection with reconnection logic"""
    trade_logger, _ = setup_logging()

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
            print(f'{prices}')
            print(f'Wallet: {TradingConfig.INITIAL_WALLET}\n')
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем.")
        print('Здесь будет повешена продажа существующих ордеров и выход в USDT')
