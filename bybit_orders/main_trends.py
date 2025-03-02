import json
import websocket
import threading
import time
from collections import deque
from log_handler import log_event, log_wallet


BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/spot"
PAIRS = ['BTCUSDT', 'ETHUSDT']
SUBSCRIPTIONS = {"op": "subscribe", "args": [f"orderbook.1.{pair}" for pair in PAIRS]}
bybit_prices = {pair: {} for pair in PAIRS}
wallet = {'balance': 1000}  # Начальный депозит 1000 USD
positions = {}
candle_history = {
    'BTCUSDT': deque(maxlen=300),
    'ETHUSDT': deque(maxlen=300)
}
trend_confirmations = {
    'BTCUSDT': {'bullish': 0, 'bearish': 0},
    'ETHUSDT': {'bullish': 0, 'bearish': 0},
}
COMMISSION = 0.001           # 0.1%
MIN_PROFIT_PCT = 0.005       # 0.5% прибыль (после вычета комиссии)
STOP_LOSS_TRIGGER = 0.01     # стоп-лосс: 1% откат от текущего максимума/минимума
CONFIRMATION_PERIODS = 3     # требуется 2-3 периода для подтверждения разворота
RISK_PERCENT = 0.02          # используем 2% депозита для расчёта позиции (при этом риск не более 20% депозита)
TRADE_FRACTION = 0.5


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
        while True:
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
                log_event(f"Ошибка запуска WebSocket: {e}")


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
    structure_bull = is_bullish_structure(candles, n=5)
    structure_bear = is_bearish_structure(candles, n=5)
    if sma50 is not None and sma200 is not None:
        if current['close'] > sma50 > sma200:
            return "bullish"
        if current['close'] < sma50 < sma200:
            return "bearish"
    if structure_bull:
        return "bullish"
    if structure_bear:
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
    investment = wallet['balance'] * TRADE_FRACTION
    atr = compute_atr(candle_history[symbol], period=14)
    qty = investment / price if atr is None or atr == 0 else investment / price
    entry_price = price * (1 + COMMISSION)
    target_price = entry_price * (1 + MIN_PROFIT_PCT)
    positions[symbol] = {
        'side': 'long',
        'entry_price': entry_price,
        'max_price': entry_price,
        'qty': qty,
        'commission': COMMISSION,
        'target_price': target_price,
        'investment': investment
    }
    wallet['balance'] -= investment
    log_event(f"{symbol}: Открыт LONG по цене {entry_price:.2f}, target {target_price:.2f}, "
              f"количество: {qty:.6f}. Инвестировано: {investment:.2f}. Остаток кошелька: {wallet['balance']:.2f}")
    log_wallet(f"Открытие LONG {symbol}: Инвестировано {investment:.2f}, новый баланс {wallet['balance']:.2f}")
    return True

def open_short(symbol, price):
    if symbol in positions and positions[symbol]['side'] == 'short':
        log_event(f"{symbol}: Шорт позиция уже открыта.")
        return False
    investment = wallet['balance'] * TRADE_FRACTION
    atr = compute_atr(candle_history[symbol], period=14)
    qty = investment / price if atr is None or atr == 0 else investment / price
    entry_price = price * (1 - COMMISSION)
    target_price = entry_price * (1 - MIN_PROFIT_PCT)
    positions[symbol] = {
        'side': 'short',
        'entry_price': entry_price,
        'min_price': entry_price,
        'qty': qty,
        'commission': COMMISSION,
        'target_price': target_price,
        'investment': investment
    }
    wallet['balance'] -= investment
    log_event(f"{symbol}: Открыт SHORT по цене {entry_price:.2f}, target {target_price:.2f}, "
              f"количество: {qty:.6f}. Инвестировано: {investment:.2f}. Остаток кошелька: {wallet['balance']:.2f}")
    log_wallet(f"Открытие SHORT {symbol}: Инвестировано {investment:.2f}, новый баланс {wallet['balance']:.2f}")
    return True

def close_position(symbol, price):
    if symbol not in positions:
        log_event(f"{symbol}: Нет открытой позиции для закрытия.")
        return False
    pos = positions[symbol]
    side = pos['side']
    qty = pos['qty']
    entry_price = pos['entry_price']
    target_price = pos.get('target_price', entry_price)
    investment = pos.get('investment', 0)
    if side == 'long':
        profit = (price - entry_price) * qty
        deviation = ((price / target_price) - 1) * 100
        log_event(f"{symbol}: Закрыт LONG по цене {price:.2f}. Прибыль: {profit:.2f}. "
                  f"Целевая цена: {target_price:.2f} (отклонение: {deviation:+.2f}%).")
    elif side == 'short':
        profit = (entry_price - price) * qty
        deviation = ((target_price / price) - 1) * 100
        log_event(f"{symbol}: Закрыт SHORT по цене {price:.2f}. Прибыль: {profit:.2f}. "
                  f"Целевая цена: {target_price:.2f} (отклонение: {deviation:+.2f}%).")
    wallet['balance'] += (investment + profit)
    log_event(f"{symbol}: Новый баланс: {wallet['balance']:.2f}")
    log_wallet(f"Закрытие {side.upper()} {symbol}: Прибыль {profit:.2f}, инвестировано {investment:.2f}, "
               f"новый баланс {wallet['balance']:.2f}")
    del positions[symbol]
    trend_confirmations[symbol] = {'bullish': 0, 'bearish': 0}
    return True

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
    if trend_confirmations[symbol]['bullish'] >= CONFIRMATION_PERIODS:
        confirmed_trend = "bullish"
    elif trend_confirmations[symbol]['bearish'] >= CONFIRMATION_PERIODS:
        confirmed_trend = "bearish"

    sma50 = compute_sma(candles, 50)
    sma200 = compute_sma(candles, 200)
    spread = ask_price - bid_price
    log_event(f"{symbol}: mid={mid_price:.2f}, SMA50={sma50 and round(sma50,2)}, "
              f"SMA200={sma200 and round(sma200,2)}, RSI={rsi and round(rsi,2)}, "
              f"Спред={spread:.2f}, Тренд: {confirmed_trend or 'неопределён'}")

    if symbol not in positions:
        if confirmed_trend == "bullish":
            open_long(symbol, ask_price)
        elif confirmed_trend == "bearish":
            open_short(symbol, bid_price)
    else:
        pos = positions[symbol]
        side = pos['side']
        if side == 'long':
            if bid_price > pos['max_price']:
                pos['max_price'] = bid_price
            take_profit_price = pos['entry_price'] * (1 + MIN_PROFIT_PCT)
            stop_loss_price = pos['max_price'] * (1 - STOP_LOSS_TRIGGER)
            if bid_price >= take_profit_price:
                log_event(f"{symbol}: LONG - Достигнут тейк-профит: bid {bid_price:.2f} >= {take_profit_price:.2f}")
                close_position(symbol, bid_price)
            elif bid_price <= stop_loss_price:
                log_event(f"{symbol}: LONG - Сработал стоп-лосс: bid {bid_price:.2f} <= {stop_loss_price:.2f}")
                close_position(symbol, bid_price)
            elif confirmed_trend == "bearish":
                log_event(f"{symbol}: LONG - Разворот тренда (bearish), закрытие позиции по bid {bid_price:.2f}.")
                close_position(symbol, bid_price)
        elif side == 'short':
            if ask_price < pos['min_price']:
                pos['min_price'] = ask_price
            take_profit_price = pos['entry_price'] * (1 - MIN_PROFIT_PCT)
            stop_loss_price = pos['min_price'] * (1 + STOP_LOSS_TRIGGER)
            if ask_price <= take_profit_price:
                log_event(f"{symbol}: SHORT - Достигнут тейк-профит: ask {ask_price:.2f} <= {take_profit_price:.2f}")
                close_position(symbol, ask_price)
            elif ask_price >= stop_loss_price:
                log_event(f"{symbol}: SHORT - Сработал стоп-лосс: ask {ask_price:.2f} >= {stop_loss_price:.2f}")
                close_position(symbol, ask_price)
            elif confirmed_trend == "bullish":
                log_event(f"{symbol}: SHORT - Разворот тренда (bullish), закрытие позиции по ask {ask_price:.2f}.")
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


if __name__ == '__main__':
    ws_thread = threading.Thread(target=run_websocket, daemon=True)
    ws_thread.start()
    while True:
        for symbol in PAIRS:
            log_event(f"{symbol}: "
                      f"Последняя свеча: {candle_history[symbol][-1] if candle_history[symbol] else 'Нет данных'}, "
                      f"Позиция: {positions.get(symbol)}")
        time.sleep(2)
