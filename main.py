import requests
import pathlib
import hmac
import hashlib
from datetime import datetime


from functions import (get_data_from_json_file, get_server_time, from_int_to_date, datetime_to_int,
                       get_historical_volatolity, get_wallet_balance, place_order)


host_testnet = 'https://api-testnet.bybit.com'
host_demo = 'https://api-demo.bybit.com'
coin = 'BTC'
path_to_api_key = pathlib.Path.cwd().joinpath('api_key.json')
path_to_api_secret = pathlib.Path.cwd().joinpath('api_secret.json')
X_BAPI_API_KEY = get_data_from_json_file(path_to_api_key)['api_key_test']
api_secret = get_data_from_json_file(path_to_api_secret)['api_key_test']

# server_time = get_server_time()
time = datetime.now()
cur_time = str(datetime_to_int(time, '%Y.%m.%d %H:%M:%S.%f'))
data_to_sign = cur_time + X_BAPI_API_KEY + '20000'
signature = hmac.new(api_secret.encode(), data_to_sign.encode(), hashlib.sha256).hexdigest()
# print(get_wallet_balance(X_BAPI_API_KEY, signature, cur_time, host_testnet))
print(place_order(X_BAPI_API_KEY, signature, cur_time, host_demo))

