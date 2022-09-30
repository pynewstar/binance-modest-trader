import requests

def get_present_price(coin):
    # 最新价
    return requests.get('https://fapi.binance.com/fapi/v1/ticker/price?symbol=%s' % coin).json()['price']

def get_history_k(coin,typ,T='4h',limit=1000,start_time=None,end_time=None):
    # 历史k线
    '''
    :param coin: 币种
    :param typ: 类型（现货/合约）
    :param T: 时间级别
    :return: 直接返回接口完整历史k线数据，默认1000条
    '''
    if typ=='现货':
        return  requests.get('https://api.binance.com/api/v1/klines?symbol=%s&interval=%s&limit=%d' % (coin,T,limit)).json()
    else:
        if start_time and end_time:
            return  requests.get('https://fapi.binance.com/fapi/v1/klines?symbol=%s&interval=%s' % (coin,T)+'&startTime=%d&endTime=%d'%(start_time,end_time)).json()
        else:
            return  requests.get('https://fapi.binance.com/fapi/v1/klines?symbol=%s&interval=%s&limit=%d' % (coin,T,limit)).json()

def get_24hr():
    # 24小时U本位数据
    return sorted([[i["symbol"],float(i["quoteVolume"]),float(i["lastPrice"]),i["volume"]] for i in requests.get('https://fapi.binance.com/fapi/v1/ticker/24hr').json()],key=lambda x:x[1],reverse=True)

def long_short_ratio(coin,T):
    # 多空人数比，"5m","15m","30m","1h","2h","4h","6h","12h","1d"
    return [float(i['longShortRatio']) for i in requests.get('https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=%s&period=%s&limit=500' % (coin, T)).json()]

def top_long_short_ratio(coin,T):
    # 大户持仓量多空比
    return [float(i['longShortRatio']) for i in requests.get('https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol=%s&period=%s&limit=500' % (coin, T)).json()]

def take_long_short_ratio(coin,T):
    # 主动买卖量比
    return requests.get('https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=%s&period=%s&limit=500' % (coin, T)).json()

if __name__ == "__main__":
    res = get_24hr()
    for i in res[:20]:
        print(i)
    # import sys
    # info = sys.argv
    # print(long_short_ratio(info[1],info[2]))
    # print(top_long_short_ratio(info[1],info[2]))
