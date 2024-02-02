import os
import sys
sys.path.append('../Libraries/trade')

import numpy as np
import pandas as pd
import random
import matplotlib.pyplot as plt
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
    
    #MA(data, Columns.CLOSE, 5)
    ATR(data, atr_window, atr_window * 2, atr_multiply)
    #ADX(data, di_window, adx_window, adx_window * 2)
    #POLARITY(data, polarity_window)
    #TREND_ADX_DI(data, 20)
    SUPERTREND(data)
        
class GeneticCode:
    DataType = int
    GeneInt: DataType = 1
    GeneFloat: DataType = 2
    GeneList: DataType = 3

    def __init__(self, gene_space):
        self.gene_space = gene_space
           
    def gen_number(self, gene_space):
        typ = gene_space[0]
        if typ == self.GeneList:
            lis = gene_space[1]
            n = len(lis)
            i = random.randint(0, n - 1)
            return lis[i]
        begin = gene_space[1]
        end = gene_space[2]
        step = gene_space[3]
        num = int((end - begin) / step) + 1
        i = random.randint(0, num - 1)
        out = begin + step * i
        if typ == self.GeneInt:
            return int(out)
        elif typ == self.GeneFloat:
            return float(out)
                
    def create_code(self):
        n = len(self.gene_space)
        code = []
        for i in range(n):
            space = self.gene_space[i]
            value = self.gen_number(space)
            code.append(value)
        return code        

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
        
    def close_auto(self, index, data):
        time = data[Columns.TIME][index]
        hi = data[Columns.HIGH][index]
        lo = data[Columns.LOW][index]
        cl = data[Columns.CLOSE][index]
        if self.closed:
            return
        profit0 = cl - self.entry_price
        profit1 = hi - self.entry_price
        profit2 = lo- self.entry_price
        if self.signal == Signal.SHORT:
            profit0 *= -1
            profit1 *= -1
            profit2 *= -2
        profit = [profit0, profit1, profit2]
        # losscut
        if np.min(profit) < - self.sl:
            if self.signal == Signal.SHORT:
                self.close(index, time, hi)
            else:
                self.close(index, time, lo)
        if profit0  > 0 and self.trailing_stop > 0:
            if self.profit_max is None:
                if profit0 > self.trailing_stop:
                    self.profit_max = profit0
                return
            else:
                if profit0 > self.profit_max:
                    self.profit_max = profit0
            
            # trailing stop
            if self.profit_max is not None:
                delta = self.profit_max - profit0
                if delta > self.trailing_stop:
                    self.close(index, time, cl)
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
    def summary(trades, save=False, plot=False):
        profit = 0 
        num = 0
        profit_max = None
        profit_min = None
        result = []
        win = 0
        for pos in trades:
            if pos.closed == False:
                continue
            profit += pos.profit
            if profit_max is None:
                if pos.profit > 0:
                    profit_max = pos.profit
                    win += 1
            else:
                if pos.profit > profit_max:
                    profit_max = pos.profit
            if profit_min is None:
                profit_min = pos.profit
            else:
                if pos.profit < profit_min:
                    profit_min = pos.profit
            num += 1
            win_rate =  float(win) / float(num)
            result.append([pos.signal, pos.entry_index, str(pos.entry_time), pos.entry_price, pos.exit_index, pos.exit_time, pos.exit_price, pos.profit, win_rate])
        if num == 0:
            return (0, 0, 0, 0, 0)
        else:
            if save:
                columns = ['Long/Short', 'entry_index', 'entry_time', 'entry_price', 'exit_index', 'exit_time', 'exit_price', 'profit', 'win_rate']
                df = pd.DataFrame(data=result, columns=columns)
            return (profit, num, profit_max, profit_min, win_rate)
            
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
            pos.close_auto(self.current, data)
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
    (profit, num, profit_max, profit_min, win_rate) = Position.summary(trades)
    print(symbol, timeframe, 'profit', profit, 'drawdown', profit_min, 'num', num, )
    
def optimize_trade(symbol, timeframe, gene_space, years, months, number, repeat=20):
    loader = DataLoader()
    n = loader.load_data(symbol, timeframe, years, months)
    if n < 200:
        print('Data size small', n, symbol, timeframe, years[0], years[-1])
        return
    data0 = loader.data()
    technical = GeneticCode(gene_space[0])
    trade = GeneticCode(gene_space[1])
    result = []
    for i in range(repeat):
        data = data0.copy()
        code = technical.create_code()
        atr_window = code[0]
        atr_multiply = code[1]
        technical_param = {'atr_window': atr_window, 'atr_multiply': atr_multiply, 'di_window': 25, 'adx_window': 25, 'polarity_window': 50}
        indicators(data, technical_param)
        for j in range(repeat):
            code = trade.create_code()
            sl = code[0]
            trailing_stop = code[1]
            trade_param =  {'sl': sl, 'trailing_stop': trailing_stop, 'volume': 0.1, 'position_max': 5, 'timelimit': 0}
            sim = TradeBotSim(symbol, timeframe, trade_param)
            sim.run(data, 200)
            while True:
                r = sim.update()
                if r == False:
                    break
            trades = sim.positions
            (profit, num, profit_max, profit_min, win_rate) = Position.summary(trades)
            result.append([symbol, timeframe, years[0], years[-1], atr_window, atr_multiply, sl, trailing_stop, profit, num, profit_min, profit + profit_min, win_rate])
            print(symbol, timeframe, 'profit', profit, 'drawdown', profit_min, 'num', num, 'win_rate', win_rate )    

    columns = ['symbol', 'timeframe', 'year_begin', 'year_end', 'atr_window', 'atr_multiply', 'sl', 'trailing_stop', 'profit', 'num', 'drawdown', 'fitness', 'win_rate']
    df = pd.DataFrame(data=result, columns=columns)
    df = df.sort_values('fitness', ascending=False)
    df.to_excel('./report/summary_' + symbol + '_' + timeframe + '_' + str(years[0]) + '-' + str(years[-1]) + '_' + str(number) + '.xlsx')

def create_gene_space(symbol, timeframe):
    gene_space = None
    if symbol == 'NIKKEI' or symbol == 'DOW':
        sl =  [GeneticCode.GeneFloat, 50, 500, 10]    
    elif symbol == 'NSDQ': #16000
        sl = [GeneticCode.GeneFloat, 20, 200, 10]
    elif symbol == 'HK50':    
        sl = [GeneticCode.GeneFloat, 50, 400, 10]
    elif symbol == 'USDJPY' or symbol == 'EURJPY':
        sl = [GeneticCode.GeneFloat, 0.05, 0.5, 0.05]
    elif symbol == 'EURUSD': #1.0
        sl = [GeneticCode.GeneFloat, 0.0005, 0.005, 0.0005]
    elif symbol == 'GBPJPY':
        sl = [GeneticCode.GeneFloat, 0.05, 0.5, 0.05]
    elif symbol == 'AUDJPY': # 100
        sl = [GeneticCode.GeneFloat, 0.025, 0.5, 0.025]
    elif symbol == 'XAUUSD': #2000
        sl = [GeneticCode.GeneFloat, 0.5, 5.0, 0.5] 
    elif symbol == 'CL': # 70
        sl = [GeneticCode.GeneFloat, 0.02, 0.5, 0.2] 
    else:
        raise Exception('Bad symbol')

    d = [0.0] + list(np.arange(sl[1], sl[2], sl[3]))
    trailing_stop = [GeneticCode.GeneList, d] 
    
    technical_space = [
                    [GeneticCode.GeneInt,   10, 100, 10],     # atr_window
                    [GeneticCode.GeneFloat, 0.2, 4.0, 0.1]   # atr_multiply
    ]
    
    trade_space = [ 
                    sl,                                       # stoploss
                    trailing_stop                                        # trailing_stop    
                ] 
    
    return technical_space, trade_space

def optimize(symbols, timeframe):
    for symbol in symbols:
        gene_space = create_gene_space(symbol, timeframe)
        t0 = datetime.now()
        optimize_trade(symbol, timeframe, gene_space, range(2020, 2024), range(1, 13), 0)
        print('Finish, Elapsed time', datetime.now() - t0, symbol, timeframe)

def main():
    args = sys.argv
    #args = ['', 'NIKKEI', 'M15']
    if len(args) < 2:
        raise Exception('Bad parameter')
    symbol = args[1]
    symbol = symbol.upper()
    timeframe = args[2]
    timeframe = timeframe.upper()
    if symbol == 'FX':
        symbols =  ['USDJPY', 'EURJPY', 'EURUSD', 'GBPJPY', 'AUDJPY']
    elif symbol == 'STOCK':
        symbols = ['NIKKEI', 'DOW', 'NSDQ', 'HK50']
    elif symbol == 'COMODITY':
        symbols =  ['XAUUSD', 'CL']
    else:
        symbols = [symbol]
    optimize(symbols, timeframe)
               
if __name__ == '__main__':
    main()