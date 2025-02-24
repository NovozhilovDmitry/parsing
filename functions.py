import json
import requests
from datetime import datetime


def get_data_from_json_file(full_path):
    """
    :param full_path: полный путь к файлу
    :return: считывание данных из json файла
    """
    with open(full_path, 'r') as json_file:
        data = json.load(json_file)
    return data


def calculate_arbitrage_profit(cycle, prices, fee_rate, min_liquidity):
    amount = 1.0
    for i in range(len(cycle) - 1):
        base = cycle[i]
        quote = cycle[i + 1]
        pair = f"{base}{quote}" if f"{base}{quote}" in prices else f"{quote}{base}"

        if pair in prices and prices[pair]["bid"] is not None and prices[pair]["ask"] is not None:
            if pair.startswith(base):
                rate = prices[pair]["ask"]
                liquidity = prices[pair]["ask"] * prices[pair]["askSize"]
            else:
                rate = 1 / prices[pair]["bid"]
                liquidity = prices[pair]["bid"] * prices[pair]["bidSize"]

            if liquidity < min_liquidity:
                print(f"Недостаточная ликвидность для {pair}, пропускаем!")
                return 0

            rate *= (1 - fee_rate)
            amount *= rate

    return amount


def get_server_time(host):
    """
    :return: возвращает такие данные {'timeSecond': '1738692213', 'timeNano': '1738692213900666676'}
    """
    _bybit_server_time = requests.get(f'{host}/v5/market/time')
    server_times = _bybit_server_time.json()['result']
    return server_times


def from_int_to_date(timestamp: int) -> str:
    """
    :param timestamp: int значение типа 1738705080000
    :return: 05.02.2025 02:38:00.000000
    """
    dt = datetime.fromtimestamp(timestamp / 1000).strftime('%d.%m.%Y %H:%M:%S.%f')
    return dt


def datetime_to_int(date_str, mask):
    """
    :param date_str: 05.02.2025 02:38:00.000000
    :param mask: "%d.%m.%Y %H:%M:%S.%f"
    :return: Преобразует дату и время в целочисленный Unix timestamp (1738705080000)
    """
    if isinstance(date_str, str):
        dt = datetime.strptime(date_str, mask)  # Преобразуем строку в datetime
        return int(dt.timestamp() * 1000)
    elif isinstance(date_str, datetime):
        return int(date_str.timestamp() * 1000)



def get_historical_volatolity(basecoin, period, host):
    """
    basecoin код валюты
    period int значение
    :return: показывает волатильность валюты за период
    """
    _address = f'{host}/v5/market/historical-volatility'
    params = {
        'category': 'option',
        'baseCoin': basecoin.upper(),
        'period': period
    }
    data = requests.get(_address, params=params)
    return data.json()


def get_wallet_balance(api_key, api_secret, current_time, host):
    """
    :param api_key: ключ API, который получили
    :param api_secret: зашифрованный секретный ключ
            hmac.new(api_secret.encode(), data_to_sign.encode(), hashlib.sha256).hexdigest()
    :param current_time: текущее числовое время
    :param host: host
    :return: retMsg, result
    """
    _url = f'{host}/v5/account/wallet-balance'
    headers = {
        'X-BAPI-API-KEY': api_key,
        'X-BAPI-TIMESTAMP': current_time,
        'X-BAPI-RECV-WINDOW': '20000',
        'X-BAPI-SIGN': api_secret,
    }
    request = requests.get(_url, headers=headers)
    try:
        return request.json()
    except json.JSONDecodeError:
        return 'Ошибка! Не удалось получить ответ от сервера. Проверьте HOST'


def place_order(api_key, api_secret, current_time, host):
    _url = f'{host}/v5/order/create'
    payload = {"category": "linear",
               "symbol": "ETHUSDT",
               "isLeverage": 0,
               "side": "Buy",
               "orderType": "Limit",
               "qty": "1",
               "price": "1000",
               "triggerPrice": None,
               "triggerDirection": None,
               "triggerBy": None,
               "orderFilter": None,
               "orderIv": None,
               "timeInForce": "GTC",
               "positionIdx": 0,
               "orderLinkId": "test-xx1",
               "takeProfit": None,
               "stopLoss": None,
               "tpTriggerBy": None,
               "slTriggerBy": None,
               "reduceOnly": False,
               "closeOnTrigger": False,
               "smpType": None,
               "mmp": None,
               "tpslMode": None,
               "tpLimitPrice": None,
               "slLimitPrice": None,
               "tpOrderType": None,
               "slOrderType": None
               }
    json_struct = json.dumps(payload)
    headers = {
        'X-BAPI-API-KEY': api_key,
        'X-BAPI-TIMESTAMP': current_time,
        'X-BAPI-RECV-WINDOW': '20000',
        'X-BAPI-SIGN': api_secret,
    }
    request = requests.post(_url, headers=headers, data=json_struct)
    try:
        return request.json()
    except json.JSONDecodeError:
        return 'Ошибка! Не удалось получить ответ от сервера. Проверьте HOST'
