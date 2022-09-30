import requests, time, json, hmac, hashlib
from urllib.parse import urlencode

class TradeApi:
    def __init__(self, who):
        api_info = json.load(open('交易api.json'))[who]
        self.api = api_info['api']
        self.secret = api_info['secret']
        self.who = who

    def change_side(self,one_side=True):
        '''更改持仓模式，默认单向'''
        path = "https://fapi.binance.com/fapi/v1/positionSide/dual"
        params = {'dualSidePosition': 'false' if one_side else 'true'}
        return self._post(path,params)

    def change_margintype(self,symbol,isolated=True):
        '''变换逐全仓，默认逐仓'''
        path = "https://fapi.binance.com/fapi/v1/marginType"
        params = {'symbol': symbol, 'marginType': 'ISOLATED' if isolated else 'CROSSED'}
        return self._post(path, params)

    def set_leverage(self, symbol, leverage):
        ''' 调整开仓杠杆'''
        path = "https://fapi.binance.com/fapi/v1/leverage"
        params = {'symbol': symbol, 'leverage': leverage}
        return self._post(path, params)

    def get_balance(self):
        '''账户余额'''
        path = "https://fapi.binance.com/fapi/v2/balance"
        return self._get(path)
    
    def get_account(self):
        '''账户信息'''
        path = "https://fapi.binance.com/fapi/v2/account"
        res = self._get(path)
        try:
            position_list = list(filter(lambda x: x['initialMargin'] != '0', res['positions']))
            return res['totalWalletBalance'], res['availableBalance'], position_list
        except:
            print(res)
            return '','', []

    def get_income(self,timestamp=None):
        '''账户损益资金流水'''
        if timestamp:
            path = "https://fapi.binance.com/fapi/v1/income?startTime=%d&endTime=%d"%(timestamp[0],timestamp[1])
        else:
            path = "https://fapi.binance.com/fapi/v1/income"
        return self._get(path)
    
    def get_positionrisk(self):
        '''用户持仓风险
        [
            {
                "entryPrice": "0.00000", // 开仓均价
                "marginType": "isolated", // 逐仓模式或全仓模式
                "isAutoAddMargin": "false",
                "isolatedMargin": "0.00000000", // 逐仓保证金
                "leverage": "10", // 当前杠杆倍数
                "liquidationPrice": "0", // 参考强平价格
                "markPrice": "6679.50671178",   // 当前标记价格
                "maxNotionalValue": "20000000", // 当前杠杆倍数允许的名义价值上限
                "positionAmt": "0.000", // 头寸数量，符号代表多空方向, 正数为多，负数为空
                "symbol": "BTCUSDT", // 交易对
                "unRealizedProfit": "0.00000000", // 持仓未实现盈亏
                "positionSide": "BOTH", // 持仓方向
                "updateTime": 1625474304765   // 更新时间
            }
        ]
        '''
        path = "https://fapi.binance.com/fapi/v2/positionRisk"
        try:
            return list(filter(lambda x:float(x['entryPrice'])>0,self._get(path)))
        except Exception as e:
            print(e)
            return []
        
    def get_history_order(self,symbol,start,end):
        '''成交历史'''
        path = "https://fapi.binance.com/fapi/v1/userTrades"
        return self._get(path,params={'symbol':symbol,'startTime':start,'endTime':end})

    def open_order(self, symbol, side, quantity, price, positionSide):
        ''' 开单
            :param side: BUY SELL
        '''
        #if self.who == 'AAA':
        if self.who == 'BBB':
            path = "https://fapi.binance.com/fapi/v1/order/test"
        else:
            path = "https://fapi.binance.com/fapi/v1/order"
        params = self._order(symbol, quantity, side, price, positionSide)
        return self._post(path, params)

    def order_reduce(self,symbol,side,positionSide,tp,quantity=None,price=None,stopPrice=None,callbackRate=1.0,activationPrice=None):
        # 止盈止损挂单
        # tp:STOP/TAKE_PROFIT/STOP_MARKET/TAKE_PROFIT_MARKET/TRAILING_STOP_MARKET
        # 跟踪回调范围[0.1,5]，百分比
        #if self.who == 'AAA':
        if self.who == 'BBB':
            path = "https://fapi.binance.com/fapi/v1/order/test"
        else:
            path = "https://fapi.binance.com/fapi/v1/order"
        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": positionSide,
            "type": tp
        }
        if tp in ['STOP','TAKE_PROFIT']:
            params["quantity"] = quantity
            params["price"] = price
            params["stopPrice"] = stopPrice
        elif tp in ['STOP_MARKET','TAKE_PROFIT_MARKET']:
            params["stopPrice"] = stopPrice
            params["closePosition"] = True  # 清仓
        elif tp == 'TRAILING_STOP_MARKET':  # 跟踪回调
            params["callbackRate"] = callbackRate
            params["activationPrice"] = activationPrice
            params["quantity"] = quantity
        return self._post(path, params)

    def check_order(self,symbol,orderId):
        '''查询订单'''
        path = "https://fapi.binance.com/fapi/v1/order"
        params = {"symbol": symbol, "orderId": orderId}
        return self._get(path, params)

    def cancel_one_order(self,symbol,orderId):
        '''撤销某订单'''
        path = "https://fapi.binance.com/fapi/v1/order"
        params = {"symbol": symbol,"orderId":orderId}
        params.update({"recvWindow": 5000})
        query = self._sign(params)
        url = "%s" % (path)
        header = {"X-MBX-APIKEY": self.api}
        return requests.delete(url, headers=header, data=query, timeout=180, verify=True).json()

    def cancel_orders(self,symbol):
        '''撤销全部订单'''
        path = "https://fapi.binance.com/fapi/v1/allOpenOrders"
        params = {"symbol": symbol}
        params.update({"recvWindow": 5000})
        query = self._sign(params)
        url = "%s" % (path)
        header = {"X-MBX-APIKEY": self.api}
        return requests.delete(url, headers=header, data=query, timeout=180, verify=True).json()

    def _order(self, symbol, quantity, side, price, positionSide):
        params = {}
        if price is not None:
            params["type"] = "LIMIT"
            params["price"] = '%.8f' % price
            params["timeInForce"] = "GTC"
        else:
            params["type"] = "MARKET"
        params["symbol"] = symbol
        params["side"] = side
        # if not closePosition:
        #     params["quantity"] = '%.8f' % quantity
        # else:
        #     params["closePosition"] = True
        #     params["type"] = "STOP_MARKET"
        #     params["stopPrice"] = price
        #     del params["price"]
        params["quantity"] = '%.8f' % quantity
        params["positionSide"] = positionSide
        return params

    def _sign(self, params={}):
        data = params.copy()
        ts = int(1000 * time.time())
        data.update({"timestamp": ts})
        h = urlencode(data)
        b = bytearray()
        b.extend(self.secret.encode())
        signature = hmac.new(b, msg=h.encode('utf-8'), digestmod=hashlib.sha256).hexdigest()
        data.update({"signature": signature})
        return data

    def _get(self, path, params={}):
        params.update({"recvWindow": 5000})
        query = urlencode(self._sign(params))
        url = "%s?%s" % (path, query)
        header = {"X-MBX-APIKEY": self.api}
        return requests.get(url, headers=header, timeout=30, verify=True).json()

    def _post(self, path, params={}):
        params.update({"recvWindow": 5000})
        query = self._sign(params)
        url = "%s" % (path)
        header = {"X-MBX-APIKEY": self.api}
        return requests.post(url, headers=header, data=query, timeout=180, verify=True).json()
