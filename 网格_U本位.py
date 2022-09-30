# 尝试量化的第一个实盘脚本，简单的自定义网格
import time, requests
from datetime import datetime, timedelta
from trade_api import TradeApi

def change_time(sec):
    base_time = datetime.strptime('1970-01-01 00:00:00.0', '%Y-%m-%d %H:%M:%S.%f')
    return str(base_time + timedelta(seconds=8 * 3600 + int(sec)))

def get_future_price(coin):
    return requests.get('https://fapi.binance.com/fapi/v1/ticker/price?symbol=%s' % coin).json()['price']

def to_log(msg):
    with open('日志-网格-U本位.txt','a+') as f:
        f.write(msg+'\n')


class GridStrategy:
    def __init__(self,symbol,price_precision,qty_precision,mid_price,min_qty,position_times=3,size=0.5):
        self.step = 0
        self.symbol = symbol+'USDT'
        self.price_precision = price_precision
        self.qty_precision = qty_precision
        self.min_qty = min_qty
        # self.free_money = free_money
        self.position_times = position_times
        # self.position_rate = position_rate / 100  # 每格仓位比例，1%
        self.grid_size = size / 100  # 网格大小（收益），0.5%
        self.start_price = mid_price  # 入场价格
        self.buy_qty = []
        self.sell_qty = []
        self.count = 0

    def spider(self):
        try:
            self.present_price = float(get_future_price(self.symbol))
        except:
            self.present_price = None

    def grid_run(self):
        trade = TradeApi()
        # trade.change_side()
        # time.sleep(1)
        # trade.change_margintype(self.symbol)
        # time.sleep(1)
        trade.set_leverage(self.symbol, self.position_times)
        time.sleep(1)
        while 1:
            self.spider()
            if self.present_price is None:
                time.sleep(20)
                continue
            if 2.473>=self.present_price and self.step==0:
                return
            if 2.55<self.present_price<self.start_price: # 只做空情形下，动态下调下限
                self.start_price *= 0.99
            # self.position_size = self.position_times * self.free_money * self.position_rate / self.present_price
            # self.position_size = round(self.position_size, self.qty_precision)
            self.position_size = self.min_qty
            left = self.start_price / (1 + self.grid_size)
            right = self.start_price * (1 + self.grid_size)
            while 1:
                time.sleep(4)
                self.spider()
                if self.present_price is None:
                    time.sleep(20)
                    continue
                limit_price = False  # 是否下限价单
                # print('当前区间:[%.*f,%.*f]，现价:%s'%(self.price_precision,left,self.price_precision,right,self.present_price))
                if self.step<100 and self.present_price <= left:
                    if self.step == 0:
                        left /= 1 + self.grid_size
                        right /= 1 + self.grid_size
                        time.sleep(5)
                        continue  # 靠这个控制只做空
                        # print('开多', end=',')
                    elif self.step > 0:
                        pass
                        # print('补多', end=',')
                    else:
                        self.count += 1
                        print('平空', end=',')
                        limit_price = False
                    if limit_price:
                        res_long = trade.open_order(self.symbol, 'BUY', self.position_size, self.present_price, 'LONG')
                    else:
                        if self.buy_qty:
                            res_long = trade.open_order(self.symbol, 'BUY', self.buy_qty.pop(), None, 'SHORT')
                        else:
                            res_long = trade.open_order(self.symbol, 'BUY', self.position_size, None, 'LONG')
                            self.sell_qty.append(self.position_size)
                    if not 'orderId' in res_long:
                        # print(res_long)
                        time.sleep(10)
                        continue
                    self.step += 1
                    right /= 1 + self.grid_size
                    left /= 1 + self.grid_size
                    # print('步数=%d，现价=%s，网格区间=[%.*f,%.*f]，已完成格子数=%d，浮亏格子数=%d' % (self.step, self.present_price, self.price_precision,left,self.price_precision, right,self.count,self.step*(self.step+1)//2))
                elif self.step>-100 and self.present_price >= right:
                    if self.step == 0:
                        # left *= 1 + self.grid_size
                        # right *= 1 + self.grid_size
                        # continue  # 靠这个控制只做多，上一分支处同理
                        print('开空', end=',')
                        # pass
                    elif self.step < 0:
                        print('补空', end=',')
                        # pass
                    else:
                        self.count += 1
                        # print('平多', end=',')
                        limit_price = False
                    if limit_price:
                        res_short = trade.open_order(self.symbol, 'SELL', self.position_size, self.present_price, 'SHORT')
                    else:
                        if self.sell_qty:
                            res_short = trade.open_order(self.symbol, 'SELL', self.sell_qty.pop(), None, 'LONG')
                        else:
                            res_short = trade.open_order(self.symbol, 'SELL', self.position_size, None, 'SHORT')
                            self.buy_qty.append(self.position_size)
                    if not 'orderId' in res_short:
                        time.sleep(10)
                        continue
                    self.step -= 1
                    left *= 1 + self.grid_size
                    right *= 1 + self.grid_size
                    # print('步数=%d，现价=%s，网格区间=[%.*f,%.*f],已完成格子数=%d，浮亏格子数=%d' % (self.step, self.present_price, self.price_precision,left, self.price_precision,right,self.count,self.step*(self.step+1)//2))
                if self.count%50==0:
                    to_log('已完成网格数:%d，未完成格子数:%d\t%s'%(self.count,self.step*(self.step+1)//2,change_time(time.time())))
                if self.step == 0:    # 清仓时重新计算格子
                    break


if __name__ == '__main__':
    # 以2%/小时的波动计，穿越格子数=log(1+2%)/log(1+每格利润)，单位时间（1小时）利润=穿越格子数×每格利润
    # 显然每格利润越高越好，但实际未来每小时波动未知，应以过去统计中最小波动计算每格利润
    # 已实现利润=已完成格子数*free_money*position_times*position_rate*1%，100×3×4%*1%=0.12U/格
    # 浮亏格子数=当前步数*（当前步数+1）/2
    # 波动太大的币绝对要降低仓位，以降低市价滑点导致的额外亏损放大
    gs = GridStrategy('FTM',5,0,mid_price=3.15,min_qty=3,position_times=50,size=0.3)
    gs.grid_run()
    # trade = TradeApi()
    # trade.limit_future_order('BTCUSDT','SELL', 0.02, None)
