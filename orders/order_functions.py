import logging
import statistics
import math


def setup_logging():
    trade_logger = logging.getLogger("trade_logger")
    trade_logger.setLevel(logging.INFO)
    console_output = logging.StreamHandler()
    trade_handler = logging.FileHandler("logs/trading_log.log")
    trade_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    trade_logger.addHandler(trade_handler)
    trade_logger.addHandler(console_output)

    trend_logger = logging.getLogger("trend_logger")
    trend_logger.setLevel(logging.INFO)
    trend_handler = logging.FileHandler("logs/trend_log.log")
    trend_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    trend_logger.addHandler(trend_handler)
    trend_logger.addHandler(console_output)

    return trade_logger, trend_logger


def is_volatility_excessive(prices, window=10, threshold=0.02):
    """Check if market volatility exceeds acceptable threshold"""
    if len(prices) < window:
        return False
    price_range = max(prices[-window:]) - min(prices[-window:])
    avg_price = statistics.mean(prices[-window:])
    return (price_range / avg_price) > threshold


def get_market_data(symbol, bybit_data):
    """Extract and validate market data from exchange feed"""
    if not bybit_data:
        return None, None, None, 0, 0

    bid = bybit_data.get("bid")
    ask = bybit_data.get("ask")

    if bid is None or ask is None:
        return None, None, None, 0, 0

    mid_price = (bid + ask) / 2.0

    if mid_price <= 0 or math.isnan(mid_price):
        return None, None, None, 0, 0

    bid_volume = sum([level[1] for level in bybit_data.get("bids", [])[:5]])
    ask_volume = sum([level[1] for level in bybit_data.get("asks", [])[:5]])

    return bid, ask, mid_price, bid_volume, ask_volume


def calculate_indicators(price_history, short_window, long_window):
    """Calculate technical indicators from price history"""
    if len(price_history) < long_window:
        return None, None, None, None

    sma_short = statistics.mean(price_history[-short_window:])
    sma_long = statistics.mean(price_history)

    sma_short_prev = statistics.mean(price_history[-short_window - 1:-1]) if len(
        price_history) > short_window + 1 else sma_short
    sma_long_prev = statistics.mean(price_history[:-1]) if len(price_history) > 1 else sma_long

    if sma_short > sma_long and sma_short_prev <= sma_long_prev:
        ma_trend = "up"
    elif sma_short < sma_long and sma_short_prev >= sma_long_prev:
        ma_trend = "down"
    else:
        ma_trend = None

    return sma_short, sma_long, sma_short_prev, sma_long_prev, ma_trend


def handle_position_exit(symbol, position_type, exit_reason, mid_price, entry_price, trade_amount,
                         trade_logger, config):
    """Process position exit with consistent logging and accounting"""
    if position_type == "long":
        profit_percent = (mid_price - entry_price) / entry_price
    else:
        profit_percent = (entry_price - mid_price) / entry_price

    net_profit = profit_percent - 2 * config.TRADING_FEE
    new_balance = trade_amount * (1 + net_profit)

    action = "ПРОДАЖА" if position_type == "long" else "ПОКУПКА"

    trade_logger.info(f"{action} ({exit_reason}): {symbol} по цене {mid_price:.6f}, "
                      f"{'прибыль' if net_profit >= 0 else 'убыток'} {net_profit * 100:.2f}%, "
                      f"новый баланс {new_balance:.2f}")
    print(f"{action} ({exit_reason}): {symbol} по цене {mid_price:.6f}, "
          f"{'прибыль' if net_profit >= 0 else 'убыток'} {net_profit * 100:.2f}%, "
          f"новый баланс {new_balance:.2f}")

    return new_balance


def check_micro_trend_exit(symbol, position_type, micro_price_history, mid_price, entry_price,
                           trade_amount, trade_logger, config):
    """Check for exit based on micro trend reversal"""
    if len(micro_price_history) < config.MICRO_WINDOW:
        return None, None

    current_micro_direction = None
    if all(micro_price_history[i] < micro_price_history[i + 1] for i in range(config.MICRO_WINDOW - 1)):
        current_micro_direction = "up"
    elif all(micro_price_history[i] > micro_price_history[i + 1] for i in range(config.MICRO_WINDOW - 1)):
        current_micro_direction = "down"

    if current_micro_direction is None:
        return None, None

    if position_type == "long" and current_micro_direction == "down":
        profit_percent = (mid_price - entry_price) / entry_price
        if profit_percent >= config.MICRO_PROFIT_THRESHOLD:
            new_balance = handle_position_exit(
                symbol, position_type, "МИКРО-РАЗВОРОТ", mid_price, entry_price,
                trade_amount, trade_logger, config
            )
            return True, new_balance

    elif position_type == "short" and current_micro_direction == "up":
        profit_percent = (entry_price - mid_price) / entry_price
        if profit_percent >= config.MICRO_PROFIT_THRESHOLD:
            new_balance = handle_position_exit(
                symbol, position_type, "МИКРО-РАЗВОРОТ", mid_price, entry_price,
                trade_amount, trade_logger, config
            )
            return True, new_balance

    return None, None


def check_quick_exit(symbol, position_type, time_in_position, mid_price, entry_price, sma_short, sma_long,
                     trade_amount, trade_logger, config):
    """Check for quick exit based on time in position and MA conditions"""
    if time_in_position < 30:
        return None, None

    if position_type == "long":
        profit_percent = (mid_price - entry_price) / entry_price
        if profit_percent >= config.MICRO_PROFIT_THRESHOLD and sma_short < sma_long:
            new_balance = handle_position_exit(
                symbol, position_type, "БЫСТРЫЙ ВЫХОД", mid_price, entry_price,
                trade_amount, trade_logger, config
            )
            return True, new_balance

    elif position_type == "short":
        profit_percent = (entry_price - mid_price) / entry_price
        if profit_percent >= config.MICRO_PROFIT_THRESHOLD and sma_short > sma_long:
            new_balance = handle_position_exit(
                symbol, position_type, "БЫСТРЫЙ ВЫХОД", mid_price, entry_price,
                trade_amount, trade_logger, config
            )
            return True, new_balance

    return None, None


def check_stop_loss(symbol, position_type, mid_price, entry_price, trade_amount, trade_logger, config):
    """Check if stop loss has been triggered"""
    if position_type == "long":
        profit_percent = (mid_price - entry_price) / entry_price
    else:
        profit_percent = (entry_price - mid_price) / entry_price

    if profit_percent <= -config.STOP_LOSS:
        new_balance = handle_position_exit(
            symbol, position_type, "СТОП-ЛОСС", mid_price, entry_price,
            trade_amount, trade_logger, config
        )
        return True, new_balance

    return None, None


def check_trend_reversal(symbol, position_type, current_direction, trend_direction, trend_start_time,
                         trend_duration, mid_price, entry_price, trade_amount, trend_logger, trade_logger,
                         config, now):
    """Check for position exit based on trend reversal"""
    trend_changed = False
    exit_triggered = False
    new_balance = None

    if position_type == "long" and current_direction == "down":
        if trend_direction != "down":
            trend_direction = "down"
            trend_start_time = now
            trend_duration = 0
            trend_logger.info(f"{symbol}: Обнаружен новый НИСХОДЯЩИЙ тренд при LONG позиции. Цена: {mid_price:.6f}")
            trend_changed = True
        else:
            trend_duration = now - trend_start_time
            trend_logger.info(
                f"{symbol}: НИСХОДЯЩИЙ тренд продолжается {trend_duration:.1f} сек. Цена: {mid_price:.6f}")

            if trend_duration >= config.TREND_REVERSAL_TIME:
                profit_percent = (mid_price - entry_price) / entry_price
                if profit_percent >= config.REVERSAL_PROFIT_THRESHOLD:
                    new_balance = handle_position_exit(
                        symbol, position_type, "РАЗВОРОТ", mid_price, entry_price,
                        trade_amount, trade_logger, config
                    )
                    exit_triggered = True
                else:
                    trend_logger.info(
                        f"{symbol}: Разворот тренда обнаружен, но прибыль ({profit_percent * 100:.2f}%)"
                        f" недостаточна для выхода (порог: {config.REVERSAL_PROFIT_THRESHOLD * 100:.2f}%)")

    elif position_type == "short" and current_direction == "up":
        if trend_direction != "up":
            trend_direction = "up"
            trend_start_time = now
            trend_duration = 0
            trend_logger.info(f"{symbol}: Обнаружен новый ВОСХОДЯЩИЙ тренд при SHORT позиции. Цена: {mid_price:.6f}")
            trend_changed = True
        else:
            trend_duration = now - trend_start_time
            trend_logger.info(
                f"{symbol}: ВОСХОДЯЩИЙ тренд продолжается {trend_duration:.1f} сек. Цена: {mid_price:.6f}")

            if trend_duration >= config.TREND_REVERSAL_TIME:
                profit_percent = (entry_price - mid_price) / entry_price
                if profit_percent >= config.REVERSAL_PROFIT_THRESHOLD:
                    new_balance = handle_position_exit(
                        symbol, position_type, "РАЗВОРОТ", mid_price, entry_price,
                        trade_amount, trade_logger, config
                    )
                    exit_triggered = True
                else:
                    trend_logger.info(
                        f"{symbol}: Разворот тренда обнаружен, но прибыль ({profit_percent * 100:.2f}%)"
                        f" недостаточна для выхода (порог: {config.REVERSAL_PROFIT_THRESHOLD * 100:.2f}%)")
    else:
        if (position_type == "long" and trend_direction == "down") or \
                (position_type == "short" and trend_direction == "up"):
            trend_direction_name = "НИСХОДЯЩИЙ" if trend_direction == "down" else "ВОСХОДЯЩИЙ"
            trend_logger.info(f"{symbol}: {trend_direction_name} тренд прерван. Цена: {mid_price:.6f}")
            trend_direction = None
            trend_start_time = None
            trend_duration = 0

    return exit_triggered, new_balance, trend_direction, trend_start_time, trend_duration, trend_changed


def check_profit_target(symbol, position_type, mid_price, entry_price, trade_amount, trade_logger, config):
    """Check if profit target has been reached"""
    if position_type == "long":
        profit_percent = (mid_price - entry_price) / entry_price
    else:
        profit_percent = (entry_price - mid_price) / entry_price

    if profit_percent >= config.PROFIT_TARGET:
        new_balance = handle_position_exit(
            symbol, position_type, "ЦЕЛЬ", mid_price, entry_price,
            trade_amount, trade_logger, config
        )
        return True, new_balance

    return None, None


def check_entry_conditions(symbol, sma_short, sma_long, mid_price, wallet,
                           bid_volume, ask_volume, price_history, trend_logger, trade_logger, config):
    """Check for new trade entry conditions"""
    if is_volatility_excessive(price_history):
        trend_logger.info(f"{symbol}: Обнаружена высокая волатильность, сделка пропущена")
        return None, None, None

    if min(bid_volume, ask_volume) < config.MIN_LIQUIDITY:
        trend_logger.info(f"{symbol}: Недостаточная ликвидность, сделка пропущена")
        return None, None, None

    if sma_short > sma_long * (1 + config.TREND_THRESHOLD):
        position_type = "long"
        trade_amount = wallet * config.POSITION_SIZE_PERCENT
        trade_logger.info(f"{symbol}: ВХОД LONG по цене {mid_price:.6f}. Баланс: {wallet - trade_amount:.2f}")
        print(f"{symbol}: ВХОД LONG по цене {mid_price:.6f}. Баланс: {wallet - trade_amount:.2f}")
        return position_type, mid_price, trade_amount

    elif sma_short < sma_long * (1 - config.TREND_THRESHOLD):
        position_type = "short"
        trade_amount = wallet * config.POSITION_SIZE_PERCENT
        trade_logger.info(f"{symbol}: ВХОД SHORT по цене {mid_price:.6f}. Баланс: {wallet - trade_amount:.2f}")
        print(f"{symbol}: ВХОД SHORT по цене {mid_price:.6f}. Баланс: {wallet - trade_amount:.2f}")
        return position_type, mid_price, trade_amount

    return None, None, None
