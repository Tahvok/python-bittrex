"""
   See https://bittrex.com/Home/Api
"""

import time
import hmac
import hashlib
import sys
try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

try:
    from Crypto.Cipher import AES
except ImportError:
    encrypted = False
else:
    import getpass
    import ast
    import json

    encrypted = True

import requests

BUY_ORDERBOOK = 'buy'
SELL_ORDERBOOK = 'sell'
BOTH_ORDERBOOK = 'both'

TRADE_FEE = 0.0025

TICKINTERVAL_ONEMIN = 'oneMin'
TICKINTERVAL_FIVEMIN = 'fiveMin'
TICKINTERVAL_HOUR = 'hour'
TICKINTERVAL_THIRTYMIN = 'thirtyMin'
TICKINTERVAL_DAY = 'Day'

ORDERTYPE_LIMIT = 'LIMIT'
ORDERTYPE_MARKET = 'MARKET'

TIMEINEFFECT_GOOD_TIL_CANCELLED = 'GOOD_TIL_CANCELLED'
TIMEINEFFECT_IMMEDIATE_OR_CANCEL = 'IMMEDIATE_OR_CANCEL'
TIMEINEFFECT_FILL_OR_KILL = 'FILL_OR_KILL'

CONDITIONTYPE_NONE = 'NONE'
CONDITIONTYPE_GREATER_THAN = 'GREATER_THAN'
CONDITIONTYPE_LESS_THAN = 'LESS_THAN'
CONDITIONTYPE_STOP_LOSS_FIXED = 'STOP_LOSS_FIXED'
CONDITIONTYPE_STOP_LOSS_PERCENTAGE = 'STOP_LOSS_PERCENTAGE'

API_URI = 'https://api.bittrex.com'

API_V3_0 = 'v3'

BASE_PATH = '/v3{path}'

PROTECTION_PUB = 'pub'  # public methods
PROTECTION_PRV = 'prv'  # authenticated methods


def encrypt(api_key, api_secret, export=True, export_fn='secrets.json'):
    cipher = AES.new(getpass.getpass(
        'Input encryption password (string will not show)'))
    api_key_n = cipher.encrypt(api_key)
    api_secret_n = cipher.encrypt(api_secret)
    api = {'key': str(api_key_n), 'secret': str(api_secret_n)}
    if export:
        with open(export_fn, 'w') as outfile:
            json.dump(api, outfile)
    return api


class Bittrex(object):
    """
    Used for requesting Bittrex with API key and API secret
    """

    def __init__(self, api_key, api_secret, calls_per_second=1):
        self.api_key = str(api_key) if api_key is not None else ''
        self.api_secret = str(api_secret) if api_secret is not None else ''
        self.call_rate = 1.0 / calls_per_second
        self.last_call = None

        uri = API_URI

        self.base_url = '{uri}{path}'.format(uri=uri, path=BASE_PATH)

    def dispatch(self, request_url, api_timestamp, body):
        request_body = body if body else ''
        signature = hashlib.sha512(request_body.encode()).hexdigest()
        pre_sign = api_timestamp + request_url + 'GET' + signature
        api_sign = hmac.new(self.api_secret.encode(), pre_sign.encode(), hashlib.sha512).hexdigest()
        response = requests.get(
            request_url,
            headers={
                'Api-Key': self.api_key.encode(),
                'Api-Timestamp': api_timestamp,
                'Api-Content-Hash': signature,
                'Api-Signature': api_sign
            },
            timeout=10
        )

        return response.json()

    def decrypt(self):
        if encrypted:
            cipher = AES.new(getpass.getpass(
                'Input decryption password (string will not show)'))
            try:
                if isinstance(self.api_key, str):
                    self.api_key = ast.literal_eval(self.api_key)
                if isinstance(self.api_secret, str):
                    self.api_secret = ast.literal_eval(self.api_secret)
            except Exception:
                pass
            self.api_key = cipher.decrypt(self.api_key).decode()
            self.api_secret = cipher.decrypt(self.api_secret).decode()
        else:
            raise ImportError('"pycrypto" module has to be installed')

    def wait(self):
        if self.last_call is None:
            self.last_call = time.time()
        else:
            now = time.time()
            passed = now - self.last_call
            if passed < self.call_rate:
                # print("sleep")
                time.sleep(self.call_rate - passed)

            self.last_call = time.time()

    def _api_query(self, protection=None, path_dict=None, options=None, body=None):
        """
        Queries Bittrex

        :param request_url: fully-formed URL to request
        :type options: dict
        :return: JSON response from Bittrex
        :rtype : dict
        """

        if not options:
            options = {}

        request_url = self.base_url
        request_url = request_url.format(path=path_dict)

        nonce = str(int(time.time() * 1000))

        request_url += urlencode(options)

        try:
            self.wait()

            return self.dispatch(request_url, nonce, body)

        except Exception as e:
            return {
                'success': False,
                'message': 'NO_API_RESPONSE',
                'result': None,
                'error': str(e)
            }

    def get_markets(self):
        """
        Used to get the open and available trading markets
        at Bittrex along with other meta data.

        1.1 Endpoint: /public/getmarkets
        2.0 NO Equivalent

        Example ::
            {'success': True,
             'message': '',
             'result': [ {'MarketCurrency': 'LTC',
                          'BaseCurrency': 'BTC',
                          'MarketCurrencyLong': 'Litecoin',
                          'BaseCurrencyLong': 'Bitcoin',
                          'MinTradeSize': 1e-08,
                          'MarketName': 'BTC-LTC',
                          'IsActive': True,
                          'Created': '2014-02-13T00:00:00',
                          'Notice': None,
                          'IsSponsored': None,
                          'LogoUrl': 'https://i.imgur.com/R29q3dD.png'},
                          ...
                        ]
            }

        :return: Available market info in JSON
        :rtype : dict
        """
        return self._api_query(path_dict='/markets')

    def get_currencies(self):
        """
        Used to get all supported currencies at Bittrex
        along with other meta data.

        Endpoint:
        1.1 /public/getcurrencies
        2.0 /pub/Currencies/GetCurrencies

        :return: Supported currencies info in JSON
        :rtype : dict
        """
        return self._api_query(path_dict='/currencies')

    def get_market_summaries(self):
        """
        Used to get the last 24 hour summary of all active exchanges

        Endpoint:
        1.1 /public/getmarketsummaries
        2.0 /pub/Markets/GetMarketSummaries

        :return: Summaries of active exchanges in JSON
        :rtype : dict
        """
        return self._api_query(path_dict='/markets/summaries')

    def get_market_summary(self, market):
        """
        Used to get the last 24 hour summary of all active
        exchanges in specific coin

        Endpoint:
        1.1 /public/getmarketsummary
        2.0 /pub/Market/GetMarketSummary

        :param market: String literal for the market(ex: BTC-XRP)
        :type market: str
        :return: Summaries of active exchanges of a coin in JSON
        :rtype : dict
        """
        return self._api_query(
            path_dict='/markets/{marketSymbol}/summary'.format(marketSymbol=market))

    def get_market_ticker(self, market):
        """
        Used to get the last 24 hour summary of all active
        exchanges in specific coin

        Endpoint:
        1.1 /public/getmarketsummary
        2.0 /pub/Market/GetMarketSummary

        :param market: String literal for the market(ex: BTC-XRP)
        :type market: str
        :return: Summaries of active exchanges of a coin in JSON
        :rtype : dict
        """
        return self._api_query(
            path_dict='/markets/{marketSymbol}/ticker'.format(marketSymbol=market))

    def buy_limit(self, market, quantity, rate):
        """
        Used to place a buy order in a specific market. Use buylimit to place
        limit orders Make sure you have the proper permissions set on your
        API keys for this call to work

        Endpoint:
        1.1 /market/buylimit
        2.0 NO Direct equivalent.  Use trade_buy for LIMIT and MARKET buys

        :param market: String literal for the market (ex: BTC-LTC)
        :type market: str
        :param quantity: The amount to purchase
        :type quantity: float
        :param rate: The rate at which to place the order.
            This is not needed for market orders
        :type rate: float
        :return:
        :rtype : dict
        """
        return self._api_query(path_dict={
            API_V1_1: '/market/buylimit',
        }, options={'market': market,
                    'quantity': quantity,
                    'rate': rate}, protection=PROTECTION_PRV)

    def sell_limit(self, market, quantity, rate):
        """
        Used to place a sell order in a specific market. Use selllimit to place
        limit orders Make sure you have the proper permissions set on your
        API keys for this call to work

        Endpoint:
        1.1 /market/selllimit
        2.0 NO Direct equivalent.  Use trade_sell for LIMIT and MARKET sells

        :param market: String literal for the market (ex: BTC-LTC)
        :type market: str
        :param quantity: The amount to sell
        :type quantity: float
        :param rate: The rate at which to place the order.
            This is not needed for market orders
        :type rate: float
        :return:
        :rtype : dict
        """
        return self._api_query(path_dict={
            API_V1_1: '/market/selllimit',
        }, options={'market': market,
                    'quantity': quantity,
                    'rate': rate}, protection=PROTECTION_PRV)

    def cancel(self, uuid):
        """
        Used to cancel a buy or sell order

        Endpoint:
        1.1 /market/cancel
        2.0 /key/market/tradecancel

        :param uuid: uuid of buy or sell order
        :type uuid: str
        :return:
        :rtype : dict
        """
        return self._api_query(path_dict={
            API_V1_1: '/market/cancel',
            API_V2_0: '/key/market/tradecancel'
        }, options={'uuid': uuid, 'orderid': uuid}, protection=PROTECTION_PRV)

    def get_open_orders(self, market=None):
        """
        Get all orders that you currently have opened.
        A specific market can be requested.

        Endpoint:
        1.1 /market/getopenorders
        2.0 /key/market/getopenorders

        :param market: String literal for the market (ie. BTC-LTC)
        :type market: str
        :return: Open orders info in JSON
        :rtype : dict
        """
        return self._api_query(path_dict={
            API_V1_1: '/market/getopenorders',
            API_V2_0: '/key/market/getopenorders'
        }, options={'market': market, 'marketname': market} if market else None, protection=PROTECTION_PRV)

    def get_balances(self):
        """
        Used to retrieve all balances from your account.

        Endpoint:
        1.1 /account/getbalances
        2.0 /key/balance/GetBalances

        Example ::
            {'success': True,
             'message': '',
             'result': [ {'Currency': '1ST',
                          'Balance': 10.0,
                          'Available': 10.0,
                          'Pending': 0.0,
                          'CryptoAddress': None},
                          ...
                        ]
            }


        :return: Balances info in JSON
        :rtype : dict
        """
        return self._api_query(path_dict={
            API_V1_1: '/account/getbalances',
            API_V2_0: '/key/balance/GetBalances'
        }, protection=PROTECTION_PRV)

    def get_balance(self, currency):
        """
        Used to retrieve the balance from your account for a specific currency

        Endpoint:
        1.1 /account/getbalance
        2.0 /key/balance/getbalance

        Example ::
            {'success': True,
             'message': '',
             'result': {'Currency': '1ST',
                        'Balance': 10.0,
                        'Available': 10.0,
                        'Pending': 0.0,
                        'CryptoAddress': None}
            }


        :param currency: String literal for the currency (ex: LTC)
        :type currency: str
        :return: Balance info in JSON
        :rtype : dict
        """
        return self._api_query(path_dict={
            API_V1_1: '/account/getbalance',
            API_V2_0: '/key/balance/getbalance'
        }, options={'currency': currency, 'currencyname': currency}, protection=PROTECTION_PRV)

    def get_deposit_address(self, currency):
        """
        Used to generate or retrieve an address for a specific currency

        Endpoint:
        1.1 /account/getdepositaddress
        2.0 /key/balance/getdepositaddress

        :param currency: String literal for the currency (ie. BTC)
        :type currency: str
        :return: Address info in JSON
        :rtype : dict
        """
        return self._api_query(path_dict={
            API_V1_1: '/account/getdepositaddress',
            API_V2_0: '/key/balance/getdepositaddress'
        }, options={'currency': currency, 'currencyname': currency}, protection=PROTECTION_PRV)

    def withdraw(self, currency, quantity, address, paymentid=None):
        """
        Used to withdraw funds from your account

        Endpoint:
        1.1 /account/withdraw
        2.0 /key/balance/withdrawcurrency

        :param currency: String literal for the currency (ie. BTC)
        :type currency: str
        :param quantity: The quantity of coins to withdraw
        :type quantity: float
        :param address: The address where to send the funds.
        :type address: str
        :param paymentid: Optional argument for memos, tags, or other supplemental information for cryptos such as XRP.
        :type paymentid: str
        :return:
        :rtype : dict
        """
        options = {
            'currency': currency,
            'quantity': quantity,
            'address': address
        }
        if paymentid:
            options['paymentid'] = paymentid
        return self._api_query(path_dict={
            API_V1_1: '/account/withdraw',
            API_V2_0: '/key/balance/withdrawcurrency'
        }, options=options, protection=PROTECTION_PRV)

    def get_order_history(self, market=None):
        """
        Used to retrieve order trade history of account

        Endpoint:
        1.1 /account/getorderhistory
        2.0 /key/orders/getorderhistory or /key/market/GetOrderHistory

        :param market: optional a string literal for the market (ie. BTC-LTC).
            If omitted, will return for all markets
        :type market: str
        :return: order history in JSON
        :rtype : dict
        """
        if market:
            return self._api_query(path_dict={
                API_V1_1: '/account/getorderhistory',
                API_V2_0: '/key/market/GetOrderHistory'
            }, options={'market': market, 'marketname': market}, protection=PROTECTION_PRV)
        else:
            return self._api_query(path_dict={
                API_V1_1: '/account/getorderhistory',
                API_V2_0: '/key/orders/getorderhistory'
            }, protection=PROTECTION_PRV)

    def get_order(self, uuid):
        """
        Used to get details of buy or sell order

        Endpoint:
        1.1 /account/getorder
        2.0 /key/orders/getorder

        :param uuid: uuid of buy or sell order
        :type uuid: str
        :return:
        :rtype : dict
        """
        return self._api_query(path_dict={
            API_V1_1: '/account/getorder',
            API_V2_0: '/key/orders/getorder'
        }, options={'uuid': uuid, 'orderid': uuid}, protection=PROTECTION_PRV)

    def get_withdrawal_history(self, currency=None):
        """
        Used to view your history of withdrawals

        Endpoint:
        1.1 /account/getwithdrawalhistory
        2.0 /key/balance/getwithdrawalhistory

        :param currency: String literal for the currency (ie. BTC)
        :type currency: str
        :return: withdrawal history in JSON
        :rtype : dict
        """

        return self._api_query(path_dict={
            API_V1_1: '/account/getwithdrawalhistory',
            API_V2_0: '/key/balance/getwithdrawalhistory'
        }, options={'currency': currency, 'currencyname': currency} if currency else None,
            protection=PROTECTION_PRV)

    def get_deposit_history(self, currency=None):
        """
        Used to view your history of deposits

        Endpoint:
        1.1 /account/getdeposithistory
        2.0 /key/balance/getdeposithistory

        :param currency: String literal for the currency (ie. BTC)
        :type currency: str
        :return: deposit history in JSON
        :rtype : dict
        """
        return self._api_query(path_dict={
            API_V1_1: '/account/getdeposithistory',
            API_V2_0: '/key/balance/getdeposithistory'
        }, options={'currency': currency, 'currencyname': currency} if currency else None,
            protection=PROTECTION_PRV)

    def list_markets_by_currency(self, currency):
        """
        Helper function to see which markets exist for a currency.

        Endpoint: /public/getmarkets

        Example ::
            >>> Bittrex(None, None).list_markets_by_currency('LTC')
            ['BTC-LTC', 'ETH-LTC', 'USDT-LTC']

        :param currency: String literal for the currency (ex: LTC)
        :type currency: str
        :return: List of markets that the currency appears in
        :rtype: list
        """
        return [market['MarketName'] for market in self.get_markets()['result']
                if market['MarketName'].lower().endswith(currency.lower())]

    def get_wallet_health(self):
        """
        Used to view wallet health

        Endpoints:
        1.1 NO Equivalent
        2.0 /pub/Currencies/GetWalletHealth

        :return:
        """
        return self._api_query(path_dict={
            API_V2_0: '/pub/Currencies/GetWalletHealth'
        }, protection=PROTECTION_PUB)

    def get_balance_distribution(self):
        """
        Used to view balance distibution

        Endpoints:
        1.1 NO Equivalent
        2.0 /pub/Currency/GetBalanceDistribution

        :return:
        """
        return self._api_query(path_dict={
            API_V2_0: '/pub/Currency/GetBalanceDistribution'
        }, protection=PROTECTION_PUB)

    def get_pending_withdrawals(self, currency=None):
        """
        Used to view your pending withdrawals

        Endpoint:
        1.1 NO EQUIVALENT
        2.0 /key/balance/getpendingwithdrawals

        :param currency: String literal for the currency (ie. BTC)
        :type currency: str
        :return: pending withdrawals in JSON
        :rtype : list
        """
        return self._api_query(path_dict={
            API_V2_0: '/key/balance/getpendingwithdrawals'
        }, options={'currencyname': currency} if currency else None,
            protection=PROTECTION_PRV)

    def get_pending_deposits(self, currency=None):
        """
        Used to view your pending deposits

        Endpoint:
        1.1 NO EQUIVALENT
        2.0 /key/balance/getpendingdeposits

        :param currency: String literal for the currency (ie. BTC)
        :type currency: str
        :return: pending deposits in JSON
        :rtype : list
        """
        return self._api_query(path_dict={
            API_V2_0: '/key/balance/getpendingdeposits'
        }, options={'currencyname': currency} if currency else None,
            protection=PROTECTION_PRV)

    def generate_deposit_address(self, currency):
        """
        Generate a deposit address for the specified currency

        Endpoint:
        1.1 NO EQUIVALENT
        2.0 /key/balance/generatedepositaddress

        :param currency: String literal for the currency (ie. BTC)
        :type currency: str
        :return: result of creation operation
        :rtype : dict
        """
        return self._api_query(path_dict={
            API_V2_0: '/key/balance/getpendingdeposits'
        }, options={'currencyname': currency}, protection=PROTECTION_PRV)

    def trade_sell(self, market=None, order_type=None, quantity=None, rate=None, time_in_effect=None,
                   condition_type=None, target=0.0):
        """
        Enter a sell order into the book
        Endpoint
        1.1 NO EQUIVALENT -- see sell_market or sell_limit
        2.0 /key/market/tradesell

        :param market: String literal for the market (ex: BTC-LTC)
        :type market: str
        :param order_type: ORDERTYPE_LIMIT = 'LIMIT' or ORDERTYPE_MARKET = 'MARKET'
        :type order_type: str
        :param quantity: The amount to purchase
        :type quantity: float
        :param rate: The rate at which to place the order.
            This is not needed for market orders
        :type rate: float
        :param time_in_effect: TIMEINEFFECT_GOOD_TIL_CANCELLED = 'GOOD_TIL_CANCELLED',
                TIMEINEFFECT_IMMEDIATE_OR_CANCEL = 'IMMEDIATE_OR_CANCEL', or TIMEINEFFECT_FILL_OR_KILL = 'FILL_OR_KILL'
        :type time_in_effect: str
        :param condition_type: CONDITIONTYPE_NONE = 'NONE', CONDITIONTYPE_GREATER_THAN = 'GREATER_THAN',
                CONDITIONTYPE_LESS_THAN = 'LESS_THAN', CONDITIONTYPE_STOP_LOSS_FIXED = 'STOP_LOSS_FIXED',
                CONDITIONTYPE_STOP_LOSS_PERCENTAGE = 'STOP_LOSS_PERCENTAGE'
        :type condition_type: str
        :param target: used in conjunction with condition_type
        :type target: float
        :return:
        """
        return self._api_query(path_dict={
            API_V2_0: '/key/market/tradesell'
        }, options={
            'marketname': market,
            'ordertype': order_type,
            'quantity': quantity,
            'rate': rate,
            'timeInEffect': time_in_effect,
            'conditiontype': condition_type,
            'target': target
        }, protection=PROTECTION_PRV)

    def trade_buy(self, market=None, order_type=None, quantity=None, rate=None, time_in_effect=None,
                  condition_type=None, target=0.0):
        """
        Enter a buy order into the book
        Endpoint
        1.1 NO EQUIVALENT -- see buy_market or buy_limit
        2.0 /key/market/tradebuy

        :param market: String literal for the market (ex: BTC-LTC)
        :type market: str
        :param order_type: ORDERTYPE_LIMIT = 'LIMIT' or ORDERTYPE_MARKET = 'MARKET'
        :type order_type: str
        :param quantity: The amount to purchase
        :type quantity: float
        :param rate: The rate at which to place the order.
            This is not needed for market orders
        :type rate: float
        :param time_in_effect: TIMEINEFFECT_GOOD_TIL_CANCELLED = 'GOOD_TIL_CANCELLED',
                TIMEINEFFECT_IMMEDIATE_OR_CANCEL = 'IMMEDIATE_OR_CANCEL', or TIMEINEFFECT_FILL_OR_KILL = 'FILL_OR_KILL'
        :type time_in_effect: str
        :param condition_type: CONDITIONTYPE_NONE = 'NONE', CONDITIONTYPE_GREATER_THAN = 'GREATER_THAN',
                CONDITIONTYPE_LESS_THAN = 'LESS_THAN', CONDITIONTYPE_STOP_LOSS_FIXED = 'STOP_LOSS_FIXED',
                CONDITIONTYPE_STOP_LOSS_PERCENTAGE = 'STOP_LOSS_PERCENTAGE'
        :type condition_type: str
        :param target: used in conjunction with condition_type
        :type target: float
        :return:
        """
        return self._api_query(path_dict={
            API_V2_0: '/key/market/tradebuy'
        }, options={
            'marketname': market,
            'ordertype': order_type,
            'quantity': quantity,
            'rate': rate,
            'timeInEffect': time_in_effect,
            'conditiontype': condition_type,
            'target': target
        }, protection=PROTECTION_PRV)

    def get_candles(self, market, tick_interval):
        """
        Used to get all tick candles for a market.

        Endpoint:
        1.1 NO EQUIVALENT
        2.0 /pub/market/GetTicks

        Example  ::
            { success: true,
              message: '',
              result:
               [ { O: 421.20630125,
                   H: 424.03951276,
                   L: 421.20630125,
                   C: 421.20630125,
                   V: 0.05187504,
                   T: '2016-04-08T00:00:00',
                   BV: 21.87921187 },
                 { O: 420.206,
                   H: 420.206,
                   L: 416.78743422,
                   C: 416.78743422,
                   V: 2.42281573,
                   T: '2016-04-09T00:00:00',
                   BV: 1012.63286332 }]
            }

        :return: Available tick candles in JSON
        :rtype: dict
        """

        return self._api_query(path_dict={
            API_V2_0: '/pub/market/GetTicks'
        }, options={
            'marketName': market, 'tickInterval': tick_interval
        }, protection=PROTECTION_PUB)

    def get_latest_candle(self, market, tick_interval):
        """
        Used to get the latest candle for the market.

        Endpoint:
        1.1 NO EQUIVALENT
        2.0 /pub/market/GetLatestTick

        Example ::
            { success: true,
              message: '',
              result:
              [ {   O : 0.00350397,
                    H : 0.00351000,
                    L : 0.00350000,
                    C : 0.00350350,
                    V : 1326.42643480,
                    T : 2017-11-03T03:18:00,
                    BV: 4.64416189 } ]
            }

        :return: Available latest tick candle in JSON
        :rtype: dict
        """

        return self._api_query(path_dict={
            API_V2_0: '/pub/market/GetLatestTick'
        }, options={
            'marketName': market, 'tickInterval': tick_interval
        }, protection=PROTECTION_PUB)
