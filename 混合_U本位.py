# 马丁微调，设置浮亏补仓次数上限，到达上限会挂上止盈单后启动下一轮新马丁
# 在浮盈时固定间隔加一倍底仓，按回调率跟踪止盈，暂定浮盈的20%，比如浮盈5%回撤至4%，可根据实际调整一个动态回调算法
# 该策略运行时长约2-3个月，收益曲线不平稳，实盘当时有4k+U，1个月收益60%，从5w的饼做多到6w9，后面持续做多，在暴跌中，该策略注定了吃灰的结局，如果能看出较大的趋势波段，此策略堪称优秀，币本位食用更佳
import time, json
from datetime import datetime, timedelta
import numpy as np
from trade_api import TradeApi
from get_kdata import *


def change_time(sec):
    base_time = datetime.strptime('1970-01-01 00:00:00.0', '%Y-%m-%d %H:%M:%S.%f')
    return str(base_time + timedelta(seconds=8 * 3600 + int(sec)))

def to_log(msg):
    with open('日志-马丁-U本位.txt','a+') as f:
        f.write(msg+'\n')

def get_future_price(coin):
    while 1:
        try:
            return requests.get('https://fapi.binance.com/fapi/v1/ticker/price?symbol=%s' % coin).json()['price']
        except Exception as e:
            to_log('获取最新价格失败\t%s\t%s'%(change_time(time.time()),e))
            time.sleep(20)


class GridStrategy:
    def __init__(self,symbol, add_times=2, who='号1'):
        """
        :param symbol: BTC
        :param price_precision: 2
        :param qty_precision: 4
        :param min_qty: 最小开仓数量
        :param profit: 清仓波动
        :param add_rate: 加仓间隔，%
        :param add_times: 加仓倍率，默认2倍
        :param T: 前高/低周期长度，默认取1min计近似最优参
        :param free_money: 限制最大本金
        """
        self.step = 0
        self.symbol = symbol[:-1]
        self.side = symbol[-1]
        self.add_times = add_times
        self.who = who
        self.avg = 0.0
        self.buy_qty = []
        self.sell_qty = []
        self.win = 0.0
        self.last_buy = 0.0
        self.last_sell = 0.0
        self.lowest_price = 100000.0    # 记录最低价用于加仓参考
        self.highest_price = 0.0        # 记录最高价
        self.base_price = 0.0           # 记录正加仓
        self.avg_tmp = 0.0              # 延迟记录均价变化
        self.max_position = 0           # 记录实盘最大仓位，供后续参考
        self.t_start = time.time()
        self.read_conf(symbol)

    def read_conf(self,symbol):
        arg_data = json.load(open('U本位参数.json'))[symbol]
        self.price_precision = arg_data['price_precision']
        self.qty_precision = arg_data['qty_precision']
        self.min_qty = arg_data['min_qty']
        self.max_add_times = arg_data['max_add_times']/2
        self.profit = arg_data['profit'] / 100
        self.add_rate = arg_data['add_rate'] / 100
        self.T = arg_data['T']
        self.position_times = arg_data['position_times']
        self.if_loss = arg_data['if_loss']
        # self.t_start = time.time() - arg_data['use_time'] * 3600

    def spider(self):
        self.present_price = float(get_future_price(self.symbol))

    def read_config(self, trade):
        if self.free_money is None:
            mybalance = trade.get_balance()
            mb = list(filter(lambda x: x['asset'] == 'USDT', mybalance))[0]
            self.free_money = float(mb['availableBalance'])

    def grid_run(self):
        trade = TradeApi(self.who)
        trade.change_side(False)
        time.sleep(1)
        trade.change_margintype(self.symbol,isolated=False)     # 全仓
        time.sleep(1)
        trade.set_leverage(self.symbol, self.position_times)
        time.sleep(1)
        t_start = time.time()
        to_log('%s U本位开始运行\t%s\t#################' % (self.symbol, change_time(time.time())))
        while 1:
            # ttt = change_time(time.time())
            # if '2021-11-12' in ttt and ttt[-7] == '8' and self.step == 0:
            #     return
            self.spider()
            if self.present_price < 36200 and self.step == 0:
                return
            time.sleep(10)
            klines2 = get_history_k('合约',self.symbol, '1m')
            price1m_low = list(map(lambda x: float(x[3]), klines2))
            price1m_high = list(map(lambda x: float(x[2]), klines2))
            self.present_price = float(klines2[-1][4])
            # self.spider()
            # time.sleep(2)
            if self.step == 0:
                self.read_conf(self.symbol+self.side)
            #     if self.side == 'auto':
            #         klines = get_future_history_k(self.symbol, '1h')
            #         low_price = min(map(lambda x: float(x[3]), klines[-self.T:]))
            #         high_price = max(map(lambda x: float(x[2]), klines[-self.T:]))
            #         self.side = '多'
            #         if high_price / self.present_price - 1 > 1 - low_price / self.present_price:  # 更靠近上方
            #             # c1 = [high_price / float(i[4]) - 1 for i in klines2]
            #             # avg = sum(c1)/len(c1)
            #             # c2 = list(filter(lambda x:x>=avg, c1))
            #             # if len(c2)<len(c1):     # 有更长的时间处在远离前高处
            #             self.side = '空'
            if time.time() // 3600 - t_start // 3600 == 1:
                t_start = time.time()
                to_log('%s U本位在跑\t%s'%(self.symbol, change_time(time.time())))
            # self.read_config(trade)
            self.position_size = self.min_qty
            # condition_money = self.free_money * self.position_rate * self.position_times > 5
            if self.side != '多':
                if self.step==0:
                    sell_condition1 = self.present_price<=min(price1m_low[-4:-1]) # 前3根k低点
                    sell_condition2 = self.present_price>=max(price1m_high[-5:-1])
                    # sell_condition2 = 0
                    # if min(price1m_low[-10:-1])<min(price1m_low[-5:-1]) and max(price1m_high[-10:-5])<max(price1m_high[-5:-1]):
                    #     sell_condition2 = self.present_price<=min((min(price1m_high[-5:-1])+min(price1m_low[-5:-1]))/2,max(price1m_high[-5:-1])*(1-(max(price1m_high[-5:-1])/min(price1m_low[-10:-1])-1)/10))
                    # if sell_condition1 or sell_condition2:
                    if sell_condition1 or sell_condition2:
                        to_log('%s开空'%self.symbol)
                        res_short = trade.open_order(self.symbol, 'SELL', self.position_size, price=None, positionSide='SHORT')
                        if not 'orderId' in res_short:
                            to_log('%s开空失败\t%s\t%s'%(self.symbol, str(res_short), change_time(time.time())))
                            time.sleep(60)
                            continue
                        self.avg = self.present_price
                        self.base_price = self.avg
                        self.last_sell = self.present_price
                        self.buy_qty.append(self.position_size)
                        self.step -= 1
                        self.win -= self.position_size*self.present_price*4e-4
                        to_log('%s当前仓位成本=%.1f，开仓价=%.3f\t%s' % (self.symbol, sum(self.buy_qty)*self.avg, self.avg, change_time(time.time())))
                elif self.step < 0:
                    condition = sum(self.buy_qty)/self.min_qty<self.max_add_times   # 限制加仓次数
                    if self.if_loss and (not condition) and self.present_price >= self.last_sell * (1+self.add_rate*np.log(1-self.step)):
                        to_log('%s平空止损' % self.symbol)
                        res_long = trade.open_order(self.symbol, 'BUY', sum(self.buy_qty), price=None, positionSide='SHORT')
                        if not 'orderId' in res_long:
                            to_log('%s平空失败\t%s\t%s' % (self.symbol, str(res_long), change_time(time.time())))
                            continue
                        self.win += sum(self.buy_qty) * (self.avg - self.present_price) * (1-4e-4)
                        self.step = 0
                        self.avg = 0.0
                        self.last_sell = 0.0
                        self.buy_qty = []
                        self.lowest_price = 100000.0
                        self.highest_price = 0.0
                        self.base_price = 0.0
                        self.avg_tmp = 0.0
                    elif condition and self.present_price >= self.last_sell * (1+self.add_rate*np.log(1-self.step)):
                        self.highest_price = max(self.present_price, self.highest_price)
                        if self.present_price <= self.highest_price*(1-(self.highest_price/self.last_sell-1)/5):
                            to_log('%s加仓'%self.symbol)
                            res_short = trade.open_order(self.symbol, 'SELL', sum(self.buy_qty), price=None, positionSide='SHORT')
                            if not 'orderId' in res_short:
                                if res_short['msg'] == 'Margin is insufficient.':
                                    to_log('%s可用金不足\t%s\t%s' % (self.symbol, str(res_short), change_time(time.time())))
                                else:
                                    to_log('%s加仓失败\t%s\t%s'%(self.symbol, str(res_short), change_time(time.time())))
                                continue
                            self.avg = (self.avg + self.present_price) / 2
                            self.last_sell = self.present_price
                            self.buy_qty.append(sum(self.buy_qty))
                            self.step -= 1
                            self.win -= self.buy_qty[-1] * self.present_price * 4e-4
                            to_log('%s当前仓位成本=%.1f，均价=%.3f，浮亏=%.2f，已实现盈利=%.2f（最大持有量=%s,%.1f小时）\t%s' % (
                                self.symbol, sum(self.buy_qty)*self.avg, self.avg, sum(self.buy_qty) * (self.avg - self.present_price), self.win,
                                self.max_position, (time.time() - self.t_start) / 3600, change_time(time.time())))
                    elif (not condition) and self.present_price >= self.last_sell * (1+self.add_rate*np.log(1-self.step)):
                        # 给本轮马丁挂上止盈，重置重新开始下一轮
                        to_log('%s 重新开始下一轮' % self.symbol)
                        res_long = trade.open_order(self.symbol, 'BUY', sum(self.buy_qty[-2:]), price=round(self.avg*(1-0.002),self.price_precision), positionSide='SHORT')
                        res_long = trade.open_order(self.symbol, 'BUY', sum(self.buy_qty[:-2]), price=round(self.avg*(1-self.profit),self.price_precision), positionSide='SHORT')
                        self.step = 0
                        self.avg = 0.0
                        self.last_sell = 0.0
                        self.buy_qty = []
                        self.lowest_price = 100000.0
                        self.highest_price = 0.0
                        self.base_price = 0.0
                        self.avg_tmp = 0.0
                    elif self.step==-1 and (self.present_price<=self.avg*(1-self.profit) or (self.present_price<=self.avg*(1-0.002) and self.lowest_price<100000)):
                        self.lowest_price = min(self.present_price, self.lowest_price)
                        if self.present_price>=self.lowest_price*(1+(1-self.lowest_price/self.avg)/5):
                            to_log('%s平空' % self.symbol)
                            res_long = trade.open_order(self.symbol, 'BUY', sum(self.buy_qty), price=None, positionSide='SHORT')
                            if not 'orderId' in res_long:
                                to_log('%s平空失败\t%s\t%s' % (self.symbol, str(res_long), change_time(time.time())))
                                continue
                            self.win += sum(self.buy_qty) * (self.avg - self.present_price) * (1-4e-4)
                            self.step = 0
                            self.avg = 0.0
                            self.last_sell = 0.0
                            self.buy_qty = []
                            self.lowest_price = 100000.0
                            self.highest_price = 0.0
                            self.base_price = 0.0
                            self.avg_tmp = 0.0
                            to_log('%s清仓，已实现盈利=%.2f（最大持有量=%s,%.1f小时）\t%s' % (self.symbol, self.win, self.max_position, (time.time() - self.t_start) / 3600, change_time(time.time())))
                        else:
                            if self.present_price<=self.base_price*(1-self.profit):
                                if self.base_price<self.avg:
                                    self.avg = self.avg_tmp
                                self.avg_tmp = (self.avg*sum(self.buy_qty)/self.buy_qty[0] + self.present_price) / (sum(self.buy_qty)/self.buy_qty[0]+1)
                                to_log('%s 浮盈加仓' % self.symbol)
                                res_short = trade.open_order(self.symbol, 'SELL', self.buy_qty[0], price=None, positionSide='SHORT')
                                if not 'orderId' in res_short:
                                    if res_short['msg'] == 'Margin is insufficient.':
                                        to_log('%s可用金不足\t%s\t%s' % (self.symbol, str(res_short), change_time(time.time())))
                                    else:
                                        to_log('%s加仓失败\t%s\t%s'%(self.symbol, str(res_short), change_time(time.time())))
                                    continue
                                self.base_price *= 1-self.profit
                                self.buy_qty.append(self.buy_qty[0])
                                self.win -= self.buy_qty[-1] * self.present_price * 4e-4
                                to_log('%s当前仓位成本=%.1f，均价=%.3f，浮盈=%.2f，已实现盈利=%.2f（最大持有量=%s,%.1f小时）\t%s' % (
                                    self.symbol, sum(self.buy_qty) * self.avg_tmp, self.avg_tmp, sum(self.buy_qty) * (self.present_price - self.avg), self.win,
                                    self.max_position, (time.time() - self.t_start) / 3600, change_time(time.time())))
                    elif self.step<-1 and self.present_price<=self.avg*(1-0.003):
                        to_log('%s平最近一次加仓' % self.symbol)
                        res_long = trade.open_order(self.symbol, 'BUY', self.buy_qty[-1], price=None, positionSide='SHORT')
                        if not 'orderId' in res_long:
                            to_log('%s平空失败\t%s\t%s' % (self.symbol, str(res_long), change_time(time.time())))
                            continue
                        nums = self.buy_qty.pop()
                        self.win += nums * (self.avg - self.present_price) * (1-4e-4)
                        self.step = -1
                        self.base_price = self.avg
                        self.highest_price = 0.0
                        self.last_sell = self.avg
                        to_log('%s剩余仓位成本=%.1f，均价=%.3f，浮盈=%.2f，已实现盈利=%.2f（最大持有量=%s,%.1f小时）\t%s' % (self.symbol, sum(self.buy_qty)*self.avg, self.avg, sum(self.buy_qty) * (self.avg - self.present_price), self.win, self.max_position, (time.time() - self.t_start) / 3600, change_time(time.time())))
                time.sleep(6)
            else:
                if self.step == 0:
                    buy_condition1 = self.present_price>=max(price1m_high[-4:-1]) # 前3根k高点
                    buy_condition2 = self.present_price<=min(price1m_high[-5:-1])
                    # buy_condition2 = 0
                    # if min(price1m_low[-10:-5])>min(price1m_low[-5:-1]) and max(price1m_high[-10:-1])>max(price1m_high[-5:-1]):
                    #     buy_condition2 = self.present_price>=max((max(price1m_high[-5:-1])+max(price1m_low[-5:-1]))/2,min(price1m_low[-5:-1])*(1+(1-min(price1m_low[-5:-1])/max(price1m_high[-10:-1]))/10))
                    if buy_condition1 or buy_condition2:
                        to_log('%s开多'%self.symbol)
                        res_long = trade.open_order(self.symbol, 'BUY', self.position_size, price=None, positionSide='LONG')
                        if not 'orderId' in res_long:
                            to_log('%s开多失败\t%s\t%s'%(self.symbol, str(res_long), change_time(time.time())))
                            time.sleep(60)
                            continue
                        self.avg = self.present_price
                        self.base_price = self.avg
                        self.sell_qty.append(self.position_size)
                        self.step += 1
                        self.last_buy = self.present_price
                        self.win -= self.position_size*self.present_price*4e-4
                        to_log('%s当前仓位成本=%.1f，开仓价=%.3f\t%s' % (self.symbol, sum(self.sell_qty)*self.avg, self.avg, change_time(time.time())))
                elif self.step > 0:
                    # condition = sum(self.sell_qty)*self.present_price<self.position_times*self.free_money/2
                    condition = sum(self.sell_qty)/self.min_qty<self.max_add_times   # 支配金额限制
                    if self.if_loss and (not condition) and self.present_price <= self.last_buy * (1-self.add_rate*np.log(1+self.step)):
                        to_log('%s平多止损'%self.symbol)
                        res_short = trade.open_order(self.symbol, 'SELL', sum(self.sell_qty), price=None, positionSide='LONG')
                        if not 'orderId' in res_short:
                            to_log('%s平多失败\t%s\t%s' % (self.symbol, str(res_short), change_time(time.time())))
                            continue
                        self.win += sum(self.sell_qty) * (self.present_price - self.avg) * (1-4e-4)
                        self.step = 0
                        self.avg = 0.0
                        self.last_buy = 0.0
                        self.sell_qty = []
                        self.lowest_price = 100000.0
                        self.highest_price = 0.0
                        self.base_price = 0.0
                        self.avg_tmp = 0.0
                    elif condition and self.present_price <= self.last_buy * (1-self.add_rate*np.log(1+self.step)):
                        self.lowest_price = min(self.present_price, self.lowest_price)
                        if self.present_price>=self.lowest_price*(1+(1-self.lowest_price/self.last_buy)/5):
                            to_log('%s加仓'%self.symbol)
                            res_long = trade.open_order(self.symbol, 'BUY', sum(self.sell_qty), price=None, positionSide='LONG')
                            if not 'orderId' in res_long:
                                if res_long['msg'] == 'Margin is insufficient.':
                                    to_log('%s可用金不足\t%s\t%s' % (self.symbol, str(res_long), change_time(time.time())))
                                else:
                                    to_log('%s加仓失败\t%s\t%s'%(self.symbol, str(res_long), change_time(time.time())))
                                continue
                            self.avg = (self.avg + self.present_price) / 2
                            self.last_buy = self.present_price
                            self.sell_qty.append(sum(self.sell_qty))
                            self.step += 1
                            self.win -= self.sell_qty[-1] * self.present_price * 4e-4
                            to_log('%s当前仓位成本=%.1f，均价=%.3f，浮亏=%.2f，已实现盈利=%.2f（最大持有量=%s,%.1f小时）\t%s' % (self.symbol, sum(self.sell_qty)*self.avg, self.avg,
                                    sum(self.sell_qty) * (self.present_price - self.avg), self.win, self.max_position, (time.time() - self.t_start) / 3600, change_time(time.time())))
                    elif (not condition) and self.present_price <= self.last_buy * (1-self.add_rate*np.log(1+self.step)):
                        to_log('%s 重新开始下一轮'%self.symbol)
                        trade.open_order(self.symbol, 'SELL', sum(self.sell_qty[-2:]), price=round(self.avg*(1+0.002),self.price_precision), positionSide='LONG')
                        trade.open_order(self.symbol, 'SELL', sum(self.sell_qty[:-2]), price=round(self.avg*(1+self.profit),self.price_precision), positionSide='LONG')
                        self.step = 0
                        self.avg = 0.0
                        self.last_buy = 0.0
                        self.sell_qty = []
                        self.lowest_price = 100000.0
                        self.highest_price = 0.0
                        self.base_price = 0.0
                        self.avg_tmp = 0.0
                    elif self.step==1 and (self.present_price>=self.avg*(1+self.profit) or (self.present_price>=self.avg*(1+0.002) and self.highest_price>0)):
                        self.highest_price = max(self.present_price, self.highest_price)
                        # 最高处回调达到止盈位置则清仓
                        if self.present_price<=self.highest_price*(1-(self.highest_price/self.avg-1)/5):  # 重仓情形考虑回本平一半或平xx%的仓位，待计算，剩下依然重仓考虑吃多少点清仓
                            to_log('%s平多' % self.symbol)
                            res_short = trade.open_order(self.symbol, 'SELL', sum(self.sell_qty), price=None, positionSide='LONG')
                            if not 'orderId' in res_short:
                                to_log('%s平多失败\t%s\t%s' % (self.symbol, str(res_short), change_time(time.time())))
                                continue
                            self.win += sum(self.sell_qty) * (self.present_price - self.avg) * (1-4e-4)
                            self.step = 0
                            self.avg = 0.0
                            self.last_buy = 0.0
                            self.sell_qty = []
                            self.lowest_price = 100000.0
                            self.highest_price = 0.0
                            self.base_price = 0.0
                            self.avg_tmp = 0.0
                            to_log('%s清仓，已实现盈利=%.2f（最大持有量=%s,%.1f小时）\t%s' % (self.symbol, self.win, self.max_position, (time.time() - self.t_start) / 3600, change_time(time.time())))
                        else:
                            if self.present_price>=self.base_price*(1+self.profit):
                                if self.base_price>self.avg:
                                    self.avg = self.avg_tmp
                                self.avg_tmp = (self.avg*sum(self.sell_qty)/self.sell_qty[0] + self.present_price) / (sum(self.sell_qty)/self.sell_qty[0]+1)
                                to_log('%s 浮盈加仓' % self.symbol)
                                res_long = trade.open_order(self.symbol, 'BUY', self.sell_qty[0], price=None, positionSide='LONG')
                                if not 'orderId' in res_long:
                                    if res_long['msg'] == 'Margin is insufficient.':
                                        to_log('%s可用金不足\t%s\t%s' % (self.symbol, str(res_long), change_time(time.time())))
                                    else:
                                        to_log('%s加仓失败\t%s\t%s'%(self.symbol, str(res_long), change_time(time.time())))
                                    continue
                                self.base_price *= 1+self.profit
                                self.sell_qty.append(self.sell_qty[0])
                                self.win -= self.sell_qty[-1] * self.present_price * 4e-4
                    elif self.step>1 and self.present_price>=self.avg*(1+0.003):
                        to_log('%s平最近一次加仓' % self.symbol)
                        res_short = trade.open_order(self.symbol, 'SELL', self.sell_qty[-1], price=None, positionSide='LONG')
                        if not 'orderId' in res_short:
                            to_log('%s平多失败\t%s\t%s' % (self.symbol, str(res_short), change_time(time.time())))
                            continue
                        nums = self.sell_qty.pop()
                        self.win += nums * (self.present_price - self.avg) * (1-4e-4)
                        self.step = 1
                        self.lowest_price = 100000.0
                        self.base_price = self.avg
                        self.last_buy = self.avg
                        to_log('%s剩余仓位成本=%.1f，均价=%.3f，浮盈=%.2f，已实现盈利=%.2f（最大持有量=%s,%.1f小时）\t%s' % (self.symbol, sum(self.sell_qty)*self.avg, self.avg, sum(self.sell_qty) * (self.present_price - self.avg), self.win, self.max_position, (time.time() - self.t_start) / 3600, change_time(time.time())))
                # time.sleep(max(2,self.rule['rateLimits'][0]['limit'] // 600))
                time.sleep(6)
            self.max_position = max(self.max_position,sum(self.buy_qty),sum(self.sell_qty))/self.min_qty


if __name__ == '__main__':
    # t = TradeApi()
    # t.cancel_orders('BNBUSDT')
    # t.limit_future_order('BNBUSDT', 'SELL', 0.06, price=490, positionSide='LONG')
    # t.limit_future_order('DOTUSDT', 'BUY', 3, price=44.5, positionSide='SHORT')
    # t.limit_future_order('DOTUSDT', 'SELL', 2, price=44, positionSide='LONG')

    # gs = GridStrategy('BTCUSDT多')
    # gs = GridStrategy('BTCUSDT_211231空')
    # gs = GridStrategy('ETHUSDT多')
    gs = GridStrategy('BTCUSDT空',who='号1')
    gs.grid_run()
