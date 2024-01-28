import os
import sys
sys.path.append('../Libraries/trade')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pytz
from datetime import datetime, timedelta, timezone
from dateutil import tz
from common import Columns, Signal, Indicators, UP, DOWN
from technical import MA, ATR, ADX, SUPERTREND, POLARITY, TREND_ADX_DI
from time_utils import TimeUtils
from utils import Utils

JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc')  

class DataLoader:
    def server_time_str_2_datetime(self, server_time_str_list, server_timezone, format='%Y-%m-%d %H:%M:%S'):
        t_utc = []
        t_jst = []
        for time_str in server_time_str_list:
            t = datetime.strptime(time_str, format)
            t = t.replace(tzinfo=server_timezone)
            utc = t.astimezone(UTC)
            t_utc.append(utc)
            jst = t.astimezone(JST)        
            t_jst.append(jst)
        return t_utc, t_jst

    def data_filepath(self, symbol, timeframe, year, month):
        path = '../MarketData/Axiory/'
        dir_path = os.path.join(path, symbol, timeframe)
        name = symbol + '_' + timeframe + '_' + str(year) + '_' + str(month).zfill(2) + '.csv'
        filepath = os.path.join(dir_path, name)
        if os.path.isfile(filepath):
            return filepath 
        else:
            return None
        
    def load_data(self, symbol, timeframe, years, months):
        dfs = []
        for year in years:
            for month in months:
                filepath = self.data_filepath(symbol, timeframe, year, month)
                if filepath is None:
                    continue
                else:
                    df = pd.read_csv(filepath)
                    dfs.append(df)
        if len(dfs) == 0:
            return 0
        df = pd.concat(dfs, ignore_index=True)
        n = len(df)
        dic = {}
        for column in df.columns:
            dic[column] = list(df[column].values)
        tzone = timezone(timedelta(hours=2))
        utc, jst = self.server_time_str_2_datetime(dic[Columns.TIME], tzone)
        dic[Columns.TIME] = utc
        dic[Columns.JST] = jst
        print(symbol, timeframe, 'Data size:', len(jst), jst[0], '-', jst[-1])
        self.dic = dic
        self.size = n
        return n
    
    def data(self):
        return self.dic
    
def indicators(data: dict, param: dict):
    atr_window = param['atr_window']
    atr_multiply = param['atr_multiply']
    di_window = param['di_window']
    adx_window = param['adx_window']
    polarity_window = param['polarity_window']
    
    MA(data, Columns.CLOSE, 5)
    ATR(data, atr_window, atr_window * 2, atr_multiply)
    ADX(data, di_window, adx_window, adx_window * 2)
    POLARITY(data, polarity_window)
    TREND_ADX_DI(data, 20)
    SUPERTREND(data)
        
class Position:
    def __init__(self, index, time, price, signal, sl, trailing_stop, timelimit):
        self.entry_index = index
        self.entry_time = time
        self.entry_price = price
        self.signal = signal
        self.sl = sl            
        self.trailing_stop = trailing_stop
        self.timelimit = timelimit
        self.closed = False
        
        self.exit_index = None
        self.exit_time = None
        self.exit_price = None
        self.profit = None
        self.profit_max = None
        
    def close_auto(self, index, time, price):
        if self.closed:
            return
        profit = price - self.entry_price
        if self.signal == Signal.SHORT:
            profit *= -1
        # losscut
        if profit < - self.sl:
            self.close(index, time, price)
        if profit > 0:
            if self.profit_max is None:
                if profit > self.trailing_stop:
                    self.profit_max = profit
                return
            else:
                if profit > self.profit_max:
                    self.profit_max = profit
            
            # trailing stop
            if self.profit_max is not None:
                delta = self.profit_max - profit
                if delta > self.trailing_stop:
                    self.close(index, time, price)
        return
    
    def close(self, index, time, price):
        self.exit_index = index
        self.exit_time = time
        self.exit_price = price
        profit = price - self.entry_price
        if self.signal == Signal.SHORT:
            profit *= -1
        self.profit = profit
        self.closed = True
        return
    
    def desc(self):
        s = 'profit:' + str(self.profit) +  ' entry:' + str(self.entry_price) + ' exit: ' + str(self.exit_price) + ' index:' + str(self.entry_time) + '...' + str(self.exit_time)
        return s
    
    @staticmethod 
    def position_num(trades):
        count = 0 
        for pos in trades:
            if pos.closed == False:
                count += 1
        return count
    
    @staticmethod 
    def summary(trades):
        profit = 0 
        num = 0
        profit_max = None
        profit_min = None
        for pos in trades:
            if pos.closed == False:
                continue
            profit += pos.profit
            if profit_max is None:
                if pos.profit > 0:
                    profit_max = pos.profit
            else:
                if pos.profit > profit_max:
                    profit_max = pos.profit
            if profit_min is None:
                profit_min = pos.profit
            else:
                if pos.profit < profit_min:
                    profit_min = pos.profit
            num += 1
            
        if num == 0:
            return (0, 0, 0, 0)
        else:
            return (profit, num, profit_max, profit_min)
            
            
class TradeBotSim:
    def __init__(self, symbol: str, timeframe: str, trade_param: dict):
        self.symbol = symbol
        self.timeframe = timeframe
        self.trade_param = trade_param
        self.positions = []
        
    def run(self, data: dict, begin_index: int):
        self.alldata = data
        self.data_size = len(data[Columns.TIME])
        self.current = begin_index

    def update(self):
        if self.current >= self.data_size - 1:
            return False
        data = Utils.sliceDict(self.alldata, 0, self.current)
        time = data[Columns.TIME]
        cl = data[Columns.CLOSE]
        for pos in self.positions:
            pos.close_auto(self.current, time[self.current], cl[self.current])
        sig = self.detect_entry(data)
        if sig == Signal.LONG or sig == Signal.SHORT:
            if self.trade_param['position_max'] > Position.position_num(self.positions):
                self.entry(data, self.current, sig)
        self.current += 1
        return True
    
    def detect_entry(self, data: dict):
        trend = data[Indicators.SUPERTREND]
        long_patterns = [[DOWN, UP], [0, UP]]
        short_patterns = [[UP, DOWN], [0, DOWN]]
        d = trend[-2:]
        for pat in long_patterns:
            if d == pat:
                return Signal.LONG
        for pat in short_patterns:
            if d == pat:
                return Signal.SHORT
        return None
        
    def entry(self, data: dict, index, signal):
        time = data[Columns.TIME]
        cl = data[Columns.CLOSE]
        price = cl[index]
        pos = Position(index, time[index], price, signal, self.trade_param['sl'], self.trade_param['trailing_stop'], self.trade_param['timelimit'])        
        self.positions.append(pos)

def backtest(symbol, timeframe):
    loader = DataLoader()
    n = loader.load_data(symbol, timeframe, [2024], [1])
    technical_param = {'atr_window': 50, 'atr_multiply': 3.0, 'di_window': 25, 'adx_window': 25, 'polarity_window': 50}
    data = loader.data()
    indicators(data, technical_param)
    trade_param =  {'sl':100, 'trailing_stop': 50, 'volume': 0.1, 'position_max': 1, 'timelimit': 0}
    sim = TradeBotSim(symbol, timeframe, trade_param)
    sim.run(data, 100)
    while True:
        r = sim.update()
        if r == False:
            break
    trades = sim.positions
    (profit, num, profit_max, profit_min) = Position.summary(trades)
    print(symbol, timeframe, 'profit', profit, 'drawdown', profit_min, 'num', num, )

def main():
    symbol = 'NIKKEI'
    timeframe = 'M15'
    backtest(symbol, timeframe)
 
if __name__ == '__main__':
    main()