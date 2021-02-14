import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False
import pandas as pd
import numpy as np
import requests
import time,json
BASE_URL_V3 = "https://api.binance.cc/api/v3"

# 爬k线价格
def get_k_data(coin_type, interval, limit_nums=1000):
    url = f"{BASE_URL_V3}/klines?symbol={coin_type.upper()}&interval={interval}&limit={limit_nums}"
    return requests.get(url, timeout=5, verify=True).json()

class BackTest:
    def __init__(self,coin_type,my_T,M,money=10000):
        self.coin_type = coin_type.upper()
        self.T = my_T
        self.M = M
        self.num = len(M)
        self.result = {'币种':coin_type}
        self.ini_money = money

    # 回测
    def back_cal(self,low_limit=84,high_limit=100):
        # 计算收益/回撤
        if 'm'==self.T[-1].lower():
            t = int(self.T[:-1])
        elif 'h'==self.T[-1].lower():
            t = int(self.T[:-1])*60
        elif 'd'==self.T[-1].lower():
            t = int(self.T[:-1])*60*24
        elif 'w'==self.T[-1].lower():
            t = int(self.T[:-1])*60*24*7
        else:
            t = int(self.T[:-1])*60*24*30
        
        # --------------------------------现货---------------------------
        def xianhuo(a):
            # 无限网格，保持持仓部分总值不变
            dd_qty = dd_price = 6
            price = [i[3] for i in self.M]
            money = self.ini_money
            # 初始币量
            coins = round(round(money*a,dd_price)/price[0]/(1+0.001),dd_qty)
            base_value = price[0]*coins # 底仓价值，以此为基准加减仓
            money_ls = [money]  # 可用+币值变动列表
            # 先买a比例的底仓
            money = round(money*(1-a),dd_price) # 可用资金剩余
            break_idx_buy,break_idx_sell = [],[]
            for i in range(1,self.num):
                if price[i]*coins < base_value: # 低于基准，买
                    if money>=round(base_value-price[i]*coins,dd_price)>=10:
                        break_idx_buy.append(i)
                        money-=round(base_value-price[i]*coins,dd_price)
                        coins+=round(round(base_value-price[i]*coins,dd_price)/price[i]/(1+0.001),dd_qty)
                elif price[i]*coins > base_value:   # 高于基准，卖
                    if coins>0:
                        if round(price[i]*coins-base_value,dd_price)>=10:
                            break_idx_sell.append(i)
                            money+=round(price[i]*coins-base_value,dd_price)
                            coins-=round(round(price[i]*coins-base_value,dd_price)/price[i]/(1+0.001),dd_qty)
                money_ls.append(money+coins*price[i]*(1-0.001))
            return [break_idx_buy,break_idx_sell],money_ls
        max_rate = -100
        max_arg = []
        # 循环只是找到最优底仓仓位而已，自定义底仓就不用循环了
        for a in range(low_limit,high_limit+1,2):
            res = xianhuo(a/100)
            profit = 100*(res[-1][-1]/self.ini_money-1)
            if profit>max_rate:
                max_rate=profit
                max_arg=[a/100,res]
        print(self.coin_type,max_arg[0])
        res = max_arg[-1]
        self.result['策略收益率(%)'] = 100*(res[-1][-1]/self.ini_money-1)
        self.result['策略日化(%)'] = round(100*(10**(np.log10(self.result['策略收益率(%)']/100+1)/(t*self.num/24/60))-1),2)
        self.result['现货日化(%)'] = round(100*(10**(np.log10(self.M[-1][3]/self.M[0][3])/(t*self.num/24/60))-1),2)
        max_back = 0
        for i in range(len(res[-1])-2):
            if res[-1][i]>res[-1][i+1]:
                max_back = max(1-min([j for j in res[-1][i+1:-1]])/res[-1][i],max_back)
        self.result['策略最大回撤(%)']=round(100*max_back,2)
        max_back_cash = 0
        for i in range(self.num-2):
            if self.M[i][-1]>self.M[i+1][-1]:
                max_back_cash = max(1-min([j[-1] for j in self.M[i+1:-1]])/self.M[i][-1],max_back_cash)
        self.result['现货最大回撤(%)']=round(100*max_back_cash,2)
        self.result['底仓比例'] = max_arg[0]
        # n期收益率均值
        miu = sum([res[-1][i+1]/res[-1][i]-1 for i in range(len(res[-1])-1)])/(len(res[-1])-1)
        # n期收益率方差
        theta = (sum([(i-miu)**2 for i in res[-1][1:]])/(len(res[-1])-1))**0.5
        self.result['收益波动值'] = round(theta,2)
        try:
            self.result['夏普率'] = round(100000*100*miu/theta,2)
        except ZeroDivisionError:
            self.result['夏普率']=0
        return res

    def draw_fig(self,point_ls,money_ls):
        plt.subplot(211)
        plt.plot([i[3] for i in self.M],color='grey',label='时间粒度=%s'%self.T)
        plt.scatter(point_ls[0],[self.M[i][3] for i in point_ls[0]],c='green',label='买点')
        plt.scatter(point_ls[1],[self.M[i][3] for i in point_ls[1]],c='red',label='卖点')
        plt.legend()
        plt.subplot(212)
        plt.plot([i for i in range(len(money_ls))],[i/self.ini_money-1 for i in money_ls],label='无限网格')
        plt.plot([self.M[i][3]/self.M[0][3]-1 for i in range(self.num)],label='拿现货')
        plt.ylabel('倍数')
        plt.xlim(0,self.num)
        plt.legend()
        plt.suptitle('币种：%s，最大回撤=%.2f%%，夏普率=%.2f'%(self.coin_type,self.result['策略最大回撤(%)'],self.result['夏普率']))
        plt.show()

if __name__ == '__main__':
    for coin in ['BTCUSDT','ETHUSDT']:
        while 1:
            try:
                M_15 = [list(map(eval,i[1:5])) for i in get_k_data(coin,'15m',1500)]    # [开盘价,最高价,最低价,收盘价]
                bt = BackTest(coin,'15m',M_15)   # 本金为可选参数，默认10000，
                p_ls,m_ls = bt.back_cal(50,60)
                print(bt.result)
                bt.draw_fig(p_ls,m_ls)
                time.sleep(0.5)
                break
            except Exception as e:
                print(e)
                time.sleep(1)
