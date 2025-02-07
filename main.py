import requests
import pathlib
from datetime import datetime
from functions import (get_data_from_json_file, get_server_time, from_int_to_date, datetime_to_int,
                       get_historical_volatolity)


# server_time = get_server_time()
date_from = '01.02.2025 23:00:00'
date_to = '01.02.2025 23:30:00'

path_to_api_key = pathlib.Path.cwd().joinpath('api_key.json')
X_BAPI_API_KEY = get_data_from_json_file(path_to_api_key)['api_key_test']
X_BAPI_TIMESTAMP = 'Временная метка UTC в миллисекундах' # что это такое?
X_BAPI_SIGN = 'подпись, полученная из параметров запроса' # что это такое?
X_Referer = 'заголовок только для пользователей брокера' # что это такое?

coin = 'BTC'
start = 1735671600000 # 01.01.2025 00:00:00.000000
end = 1736017200000 # 05.01.2025 00:00:00.000000
