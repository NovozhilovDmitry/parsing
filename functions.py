import json
import requests
from datetime import datetime


HOST = 'https://api-testnet.bybit.com'
VERSION = 'v5'
PRODUCT = 'market'


def get_data_from_json_file(full_path):
    """
    :param full_path: полный путь к файлу
    :return: считывание данных из json файла
    """
    with open(full_path, 'r') as json_file:
        data = json.load(json_file)
    return data


def get_server_time(host=HOST, version=VERSION, product=PRODUCT):
    """
    :return: возвращает такие данные {'timeSecond': '1738692213', 'timeNano': '1738692213900666676'}
    """
    _bybit_server_time = requests.get(f'{host}/{version}/{product}/time')
    server_times = _bybit_server_time.json()['result']
    return server_times


def from_int_to_date(timestamp: int) -> str:
    """
    :param timestamp: int значение типа 1738705080000
    :return: 05.02.2025 02:38:00.000000
    """
    dt = datetime.fromtimestamp(timestamp / 1000).strftime('%d.%m.%Y %H:%M:%S.%f')
    return dt


def datetime_to_int(date_str: str) -> int:
    """
    :param date_str: 05.02.2025 02:38:00.000000
    :return: Преобразует дату и время в целочисленный Unix timestamp (1738705080000)
    """
    dt = datetime.strptime(date_str, "%d.%m.%Y %H:%M:%S.%f")  # Преобразуем строку в datetime
    return int(dt.timestamp() * 1000)


def get_historical_volatolity(basecoin, period, host=HOST, version=VERSION, product=PRODUCT):
    """
    basecoin код валюты
    period int значение
    :return: показывает волатильность валюты за период
    """
    _address = f'{host}/{version}/{product}/historical-volatility'
    params = {
        'category': 'option',
        'baseCoin': basecoin.upper(),
        'period': period
    }
    data = requests.get(_address, params=params)
    return data.json()

