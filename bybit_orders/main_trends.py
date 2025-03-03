import signal
import json
import websocket
import threading
import time
import os
from collections import deque
from log_handler import log_event, log_wallet

BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/spot"
PAIRS = ['BTCUSDT', 'ETHUSDT']
SUBSCRIPTIONS = {"op": "subscribe", "args": [f"orderbook.1.{pair}" for pair in PAIRS]}
bybit_prices = {pair: {} for pair in PAIRS}

wallet = {'balance': 1000}  # Начальный депозит 1000 USD
positions = {}
candle_history = {
    'BTCUSDT': deque(maxlen=1000),
    'ETHUSDT': deque(maxlen=1000)
}
trend_confirmations = {
    'BTCUSDT': {'bullish': 0, 'bearish': 0},
    'ETHUSDT': {'bullish': 0, 'bearish': 0},
}

COMMISSION = 0.001         # 0.1%
MIN_PROFIT_PCT = 0.01      # 1% прибыль (после вычета комиссии)
STOP_LOSS_TRIGGER = 0.01   # стоп-лосс: 1% откат от текущего максимума/минимума
CONFIRMATION_PERIODS = 10  # требуется 10 периодов подтверждения разворота
RISK_PER_TRADE = 0.03      # 3% депозита на одну сделку
ADX_THRESHOLD = 30         # Минимальное значение ADX для подтверждения тренда

class BybitWebSocket:
    def __init__(self, prices):
        self.ws = None
        self.prices = prices
        self.reconnect = True

    def on_open(self, ws):
        log_event("Подключено к WebSocket Bybit")
        ws.send(json.dumps(SUBSCRIPTIONS))
        log_event(f"Отправлена подписка: {SUBSCRIPTIONS}")

    def on_message(self, ws, message):
        try:
            websocket_message_handler(message)
        except Exception as e:
            log_event(f"Ошибка обработки сообщения: {e}")

    def on_error(self, ws, error):
        log_event(f"Ошибка WebSocket Bybit: {error}")
        self.clear_prices()

    def on_close(self, ws, close_status_code, close_msg):
        log_event(f"WebSocket закрыт: {close_status_code}, {close_msg}")
        if self.reconnect:
            log_event("Переподключение через 5 сек...")
            time.sleep(5)
            self.start()

    def clear_prices(self):
        for symbol in self.prices:
            if "bybit" in self.prices[symbol]:
                del self.prices[symbol]["bybit"]

    def start(self):
        while self.reconnect:
            try:
                self.ws = websocket.WebSocketApp(
                    BYBIT_WS_URL,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close
                )
                self.ws.run_forever()
            except Exception as e:
                log_event(f"Ошибка WebSocket: {e}. Переподключение через 10 сек...")
                time.sleep(10)

def compute_sma(candles, period):
    if len(candles) < period:
        return None
    closes = [c['close'] for c in list(candles)[-period:]]
    return sum(closes) / period

def compute_atr(candles, period=14):
    if len(candles) < period + 1:
        return None
    trs = []
    candles_list = list(candles)
    for i in range(1, period+1):
        current = candles_list[-i]
        prev = candles_list[-i-1]
        tr = max(
            current['high'] - current['low'],
            abs(current['high'] - prev['close']),
            abs(current['low'] - prev['close'])
        )
        trs.append(tr)
    return sum(trs) / period

def compute_rsi(candles, period=14):
    if len(candles) < period + 1:
        return None
    gains = []
    losses = []
    candles_list = list(candles)
    for i in range(1, period+1):
        change = candles_list[-i]['close'] - candles_list[-i-1]['close']
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def compute_adx(candles, period=14):
    if len(candles) < 2 * period:
        return None
    candles_list = list(candles)
    plus_dm = []
    minus_dm = []
    tr = []
    for i in range(1, period + 1):
        current = candles_list[-i]
        prev = candles_list[-i-1]
        up_move = current['high'] - prev['high']
        down_move = prev['low'] - current['low']
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0)
        tr.append(max(current['high'] - current['low'], abs(current['high'] - prev['close']),
                      abs(current['low'] - prev['close'])))
    atr = sum(tr) / period
    plus_di = (sum(plus_dm) / atr) * 100
    minus_di = (sum(minus_dm) / atr) * 100
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100 if (plus_di + minus_di) != 0 else 0
    return dx

def is_bullish_structure(candles, n=5):
    if len(candles) < n:
        return False
    candles_list = list(candles)[-n:]
    highs = [c['high'] for c in candles_list]
    lows = [c['low'] for c in candles_list]
    return all(highs[i] < highs[i+1] for i in range(len(highs)-1)) and all(lows[i] < lows[i+1] for i in range(len(lows)-1))

def is_bearish_structure(candles, n=5):
    if len(candles) < n:
        return False
    candles_list = list(candles)[-n:]
    highs = [c['high'] for c in candles_list]
    lows = [c['low'] for c in candles_list]
    return all(highs[i] > highs[i+1] for i in range(len(highs)-1)) and all(lows[i] > lows[i+1] for i in range(len(lows)-1))

def determine_trend(candles):
    current = candles[-1]
    sma50 = compute_sma(candles, 50)
    sma200 = compute_sma(candles, 200)
    rsi = compute_rsi(candles, 14)
    adx = compute_adx(candles, 14)
    strong_trend = adx is not None and adx > ADX_THRESHOLD

    if sma50 and sma200:
        if current['close'] > sma50 > sma200 and strong_trend and (rsi is not None and rsi < 70):
            return "bullish"
        if current['close'] < sma50 < sma200 and strong_trend and (rsi is not None and rsi > 30):
            return "bearish"
    return "neutral"

def update_candle_history(symbol, price):
    candle = {
        'open': price,
        'high': price,
        'low': price,
        'close': price,
        'volume': 0,
        'timestamp': time.time()
    }
    candle_history[symbol].append(candle)

def open_long(symbol, price):
    if symbol in positions and positions[symbol]['side'] == 'long':
        log_event(f"{symbol}: Лонг позиция уже открыта.")
        return False
    if wallet['balance'] <= 0:
        log_event(f"{symbol}: Недостаточно средств для открытия позиции")
        return False
    investment = wallet['balance'] * RISK_PER_TRADE
    entry_price = price * (1 + COMMISSION)
    qty = (investment * (1 - COMMISSION)) / entry_price
    target_price = entry_price * (1 + MIN_PROFIT_PCT)
    positions[symbol] = {
        'side': 'long',
        'entry_price': entry_price,
        'max_price': entry_price,
        'qty': qty,
        'commission': COMMISSION,
        'target_price': target_price,
        'investment': investment,
        'current_profit_pct': 0.0,
        'stop_loss_pct': -0.5
    }
    wallet['balance'] -= investment
    log_event(f"{symbol}: Открыт LONG по цене {entry_price:.2f}, target {target_price:.2f}, количество: {qty:.6f}. Инвестировано: {investment:.2f}. Остаток: {wallet['balance']:.2f}")
    log_wallet(f"Открытие LONG {symbol}: Инвестировано {investment:.2f}, новый баланс {wallet['balance']:.2f}")
    return True

def open_short(symbol, price):
    if symbol in positions and positions[symbol]['side'] == 'short':
        log_event(f"{symbol}: Шорт позиция уже открыта.")
        return False
    if wallet['balance'] <= 0:
        log_event(f"{symbol}: Недостаточно средств для открытия позиции")
        return False
    investment = wallet['balance'] * RISK_PER_TRADE
    entry_price = price * (1 - COMMISSION)
    qty = (investment * (1 - COMMISSION)) / entry_price
    target_price = entry_price * (1 - MIN_PROFIT_PCT)
    positions[symbol] = {
        'side': 'short',
        'entry_price': entry_price,
        'min_price': entry_price,
        'qty': qty,
        'commission': COMMISSION,
        'target_price': target_price,
        'investment': investment,
        'current_profit_pct': 0.0,
        'stop_loss_pct': -0.5
    }
    wallet['balance'] -= investment
    log_event(f"{symbol}: Открыт SHORT по цене {entry_price:.2f}, target {target_price:.2f}, количество: {qty:.6f}. Инвестировано: {investment:.2f}. Остаток: {wallet['balance']:.2f}")
    log_wallet(f"Открытие SHORT {symbol}: Инвестировано {investment:.2f}, новый баланс {wallet['balance']:.2f}")
    return True

def close_position(symbol, price):
    if symbol not in positions:
        log_event(f"{symbol}: Нет открытой позиции для закрытия.")
        return False
    if wallet['balance'] < 0:
        log_event("ОШИБКА: Отрицательный баланс! Принудительный выход.")
        os._exit(1)
    pos = positions[symbol]
    side = pos['side']
    qty = pos['qty']
    entry_price = pos['entry_price']
    target_price = pos.get('target_price', entry_price)
    investment = pos.get('investment', 0)
    if side == 'long':
        profit = (price - entry_price) * qty
        deviation = ((price / target_price) - 1) * 100
    elif side == 'short':
        profit = (entry_price - price) * qty
        deviation = ((target_price / price) - 1) * 100
    wallet['balance'] += (investment + profit)
    log_event(f"{symbol}: Закрыт {side.upper()} по цене {price:.2f}. Прибыль: {profit:.2f}. Цель: {target_price:.2f} (отклонение: {deviation:+.2f}%). Новый баланс: {wallet['balance']:.2f}")
    log_wallet(f"Закрытие {side.upper()} {symbol}: Прибыль {profit:.2f}, инвестировано {investment:.2f}, новый баланс {wallet['balance']:.2f}")
    del positions[symbol]
    trend_confirmations[symbol] = {'bullish': 0, 'bearish': 0}
    return True

def update_stop_loss(pos, price):
    if pos['side'] == 'long':
        profit_pct = ((price - pos['entry_price']) / pos['entry_price']) * 100
        steps = int(profit_pct / 0.5)
        new_stop_pct = -0.5 + (steps * 0.25)
        if new_stop_pct > pos['stop_loss_pct']:
            pos['stop_loss_pct'] = new_stop_pct
            log_event(f"LONG: Стоп-лосс сдвинут до {new_stop_pct:.2f}% при прибыли {profit_pct:.2f}%")
    elif pos['side'] == 'short':
        profit_pct = ((pos['entry_price'] - price) / pos['entry_price']) * 100
        steps = int(profit_pct / 0.5)
        new_stop_pct = -0.5 + (steps * 0.25)
        if new_stop_pct > pos['stop_loss_pct']:
            pos['stop_loss_pct'] = new_stop_pct
            log_event(f"SHORT: Стоп-лосс сдвинут до {new_stop_pct:.2f}% при прибыли {profit_pct:.2f}%")
    pos['current_profit_pct'] = profit_pct

def on_new_price(symbol, bid_price, ask_price):
    mid_price = (bid_price + ask_price) / 2
    update_candle_history(symbol, mid_price)
    candles = candle_history[symbol]
    if len(candles) < 50:
        return

    current_trend = determine_trend(candles)
    rsi = compute_rsi(candles, period=14)
    if current_trend == "bullish":
        trend_confirmations[symbol]['bullish'] += 1
        trend_confirmations[symbol]['bearish'] = 0
    elif current_trend == "bearish":
        trend_confirmations[symbol]['bearish'] += 1
        trend_confirmations[symbol]['bullish'] = 0
    else:
        trend_confirmations[symbol]['bullish'] = 0
        trend_confirmations[symbol]['bearish'] = 0

    confirmed_trend = None
    adx_value = compute_adx(candles)
    log_event(f"ADX={adx_value and round(adx_value, 2)}")
    if adx_value is not None and adx_value < ADX_THRESHOLD:
        log_event(f"{symbol}: Боковик (ADX <{ADX_THRESHOLD}), пропуск сделки")
        return
    if trend_confirmations[symbol]['bullish'] >= CONFIRMATION_PERIODS and adx_value > ADX_THRESHOLD:
        confirmed_trend = "bullish"
    elif trend_confirmations[symbol]['bearish'] >= CONFIRMATION_PERIODS and adx_value > ADX_THRESHOLD:
        confirmed_trend = "bearish"

    sma50 = compute_sma(candles, 50)
    sma200 = compute_sma(candles, 200)
    spread = ask_price - bid_price
    log_event(f"{symbol}: mid={mid_price:.2f}, SMA50={sma50 and round(sma50,2)}, SMA200={sma200 and round(sma200,2)}, RSI={rsi and round(rsi,2)}, Спред={spread:.2f}, Тренд: {confirmed_trend or 'неопределён'}")

    if wallet['balance'] > 0 and symbol not in positions:
        if confirmed_trend == "bullish":
            open_long(symbol, ask_price)
        elif confirmed_trend == "bearish":
            open_short(symbol, bid_price)
    else:
        pos = positions.get(symbol)
        if pos:
            side = pos['side']
            if side == 'long':
                update_stop_loss(pos, bid_price)
                stop_loss_price = pos['entry_price'] * (1 + pos['stop_loss_pct'] / 100)
                if bid_price <= stop_loss_price:
                    log_event(f"{symbol}: LONG - Стоп-лосс сработал: bid {bid_price:.2f} <= {stop_loss_price:.2f}")
                    close_position(symbol, bid_price)
                elif bid_price >= pos['target_price']:
                    log_event(f"{symbol}: LONG - Тейк-профит достигнут: bid {bid_price:.2f} >= {pos['target_price']:.2f}")
                    close_position(symbol, bid_price)
                elif confirmed_trend == "bearish":
                    log_event(f"{symbol}: LONG - Разворот тренда (bearish), закрытие позиции по bid {bid_price:.2f}")
                    close_position(symbol, bid_price)
            elif side == 'short':
                update_stop_loss(pos, ask_price)
                stop_loss_price = pos['entry_price'] * (1 - pos['stop_loss_pct'] / 100)
                if ask_price >= stop_loss_price:
                    log_event(f"{symbol}: SHORT - Стоп-лосс сработал: ask {ask_price:.2f} >= {stop_loss_price:.2f}")
                    close_position(symbol, ask_price)
                elif ask_price <= pos['target_price']:
                    log_event(f"{symbol}: SHORT - Тейк-профит достигнут: ask {ask_price:.2f} <= {pos['target_price']:.2f}")
                    close_position(symbol, ask_price)
                elif confirmed_trend == "bullish":
                    log_event(f"{symbol}: SHORT - Разворот тренда (bullish), закрытие позиции по ask {ask_price:.2f}")
                    close_position(symbol, ask_price)

def websocket_message_handler(message):
    try:
        data = json.loads(message)
        if "success" in data and data["success"]:
            log_event(f"Подписка успешна: {data}")
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
                    bybit_prices[symbol]["bybit"] = {"bid": bid_price, "ask": ask_price}
                on_new_price(symbol, bid_price, ask_price)
    except Exception as e:
        log_event(f"Ошибка в websocket_message_handler: {e}")

def run_websocket():
    ws_client = BybitWebSocket(bybit_prices)
    ws_client.start()

def shutdown_trading(signum, frame):
    log_event("Получен сигнал завершения. Закрываем все открытые позиции...")
    for symbol in list(positions.keys()):
        if candle_history[symbol]:
            price = candle_history[symbol][-1]['close']
        elif symbol in bybit_prices and "bybit" in bybit_prices[symbol]:
            price = (bybit_prices[symbol]["bybit"]["bid"] + bybit_prices[symbol]["bybit"]["ask"]) / 2
        else:
            price = None
        if price is not None:
            close_position(symbol, price)
    log_wallet(f"Завершение работы. Итоговая сумма в кошельке: {wallet['balance']:.2f}")
    exit(0)

signal.signal(signal.SIGINT, shutdown_trading)
signal.signal(signal.SIGTERM, shutdown_trading)

if __name__ == '__main__':
    ws_thread = threading.Thread(target=run_websocket, daemon=True)
    ws_thread.start()
    while True:
        for symbol in PAIRS:
            log_event(f"{symbol}: Последняя свеча: {candle_history[symbol][-1] if candle_history[symbol] else 'Нет данных'}, Позиция: {positions.get(symbol)}")
        time.sleep(2)
