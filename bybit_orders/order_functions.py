import time
from log_handler import log_event


def open_long(symbol, price, wallet, positions):
    """
    Функция для открытия лонг-позиции на всю сумму кошелька.
    Вычисляет количество монет, устанавливает стоп-лосс на -0,5%,
    обновляет wallet и записывает данные позиции.
    """
    if symbol in positions:
        log_event(f"Позиция для {symbol} уже открыта.")
        return False
    investment = wallet['balance']
    if investment <= 0:
        log_event("Недостаточно средств для открытия позиции.")
        return False
    amount = investment / price
    stop_loss = price * 0.995  # стоп-лосс для лонга: -0,5%
    positions[symbol] = {
        'side': 'long',
        'entry_price': price,
        'amount': amount,
        'stop_loss': stop_loss,
        'investment': investment
    }
    wallet['balance'] = 0  # полностью инвестируем средства
    log_event(
        f"Открытие ЛОНГ позиции для {symbol}: цена входа {price}, количество {amount:.6f}, стоп-лосс {stop_loss:.2f}. Инвестировано: {investment}")
    return True


def open_short(symbol, price, wallet, positions):
    """
    Функция для открытия шорт-позиции на всю сумму кошелька.
    Вычисляет количество монет, устанавливает стоп-лосс (цена не должна подняться выше входной на 0,5%),
    обновляет wallet и записывает данные позиции.
    """
    if symbol in positions:
        log_event(f"Позиция для {symbol} уже открыта.")
        return False
    investment = wallet['balance']
    if investment <= 0:
        log_event("Недостаточно средств для открытия позиции.")
        return False
    amount = investment / price
    stop_loss = price * 1.005  # стоп-лосс для шорта: +0,5% от входной цены
    positions[symbol] = {
        'side': 'short',
        'entry_price': price,
        'amount': amount,
        'stop_loss': stop_loss,
        'investment': investment
    }
    wallet['balance'] = 0
    log_event(
        f"Открытие ШОРТ позиции для {symbol}: цена входа {price}, количество {amount:.6f}, стоп-лосс {stop_loss:.2f}. Инвестировано: {investment}")
    return True


def close_position(symbol, price, wallet, positions):
    """
    Функция для закрытия открытой позиции.
    Для лонга: пересчитывает баланс как количество монет * цену выхода.
    Для шорта: баланс = инвестиция + (входная цена - цена выхода) * количество.
    Логирует операцию и обновляет wallet.
    """
    if symbol not in positions:
        log_event(f"Нет открытой позиции для {symbol} для закрытия.")
        return False
    position = positions[symbol]
    side = position['side']
    amount = position['amount']
    entry_price = position['entry_price']
    investment = position['investment']

    if side == 'long':
        new_balance = amount * price
        profit_loss = new_balance - investment
    elif side == 'short':
        new_balance = investment + (entry_price - price) * amount
        profit_loss = new_balance - investment
    else:
        log_event("Неизвестная сторона позиции.")
        return False

    log_event(
        f"Закрытие {side.upper()} позиции для {symbol}: цена выхода {price}, баланс обновлён с {investment} до {new_balance:.2f}, прибыль/убыток: {profit_loss:.2f}")
    wallet['balance'] = new_balance
    del positions[symbol]
    return True


def analyze_trend(symbol, price_history):
    """
    Функция анализирует историю цен и вычисляет процентное изменение.
    Если цена выросла более чем на 0,5% за период, сигнал лонга;
    если упала более чем на 0,5% – сигнал шорта; иначе - нейтрально.
    """
    prices = list(price_history[symbol])
    if len(prices) < 2:
        return None  # недостаточно данных для анализа
    start_price = prices[0]['price']
    end_price = prices[-1]['price']
    change = (end_price - start_price) / start_price * 100
    if change <= -0.5:
        return 'short'
    elif change >= 0.5:
        return 'long'
    else:
        return 'neutral'


def on_new_price(symbol, price, price_history, positions, wallet):
    """
    Обрабатывает новое значение цены:
    - Добавляет цену в историю;
    - Если позиция открыта, проверяет условия стоп-лосса или разворота тренда;
    - Если позиции нет, анализирует тренд и открывает позицию при сигнале.
    """
    price_history[symbol].append({'price': price, 'time': time.time()})

    if symbol in positions:
        position = positions[symbol]
        side = position['side']
        stop_loss = position['stop_loss']

        if side == 'long':
            if price <= stop_loss:
                log_event(f"{symbol}: Цена опустилась ниже стоп-лосса для ЛОНГ позиции: {price} <= {stop_loss}")
                close_position(symbol, price, wallet, positions)
                return
            current_trend = analyze_trend(symbol, price_history)
            if current_trend == 'short':
                log_event(f"{symbol}: Тренд изменился на ШОР для ЛОНГ позиции, закрытие позиции.")
                close_position(symbol, price, wallet, positions)
                return
        elif side == 'short':
            if price >= stop_loss:
                log_event(f"{symbol}: Цена поднялась выше стоп-лосса для ШОР позиции: {price} >= {stop_loss}")
                close_position(symbol, price, wallet, positions)
                return
            current_trend = analyze_trend(symbol, price_history)
            if current_trend == 'long':
                log_event(f"{symbol}: Тренд изменился на ЛОНГ для ШОР позиции, закрытие позиции.")
                close_position(symbol, price, wallet, positions)
                return
    else:
        current_trend = analyze_trend(symbol, price_history)
        if current_trend == 'long':
            open_long(symbol, price, wallet, positions)
        elif current_trend == 'short':
            open_short(symbol, price, wallet, positions)
