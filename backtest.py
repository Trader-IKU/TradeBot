import os
import sys
sys.path.append('../Libraries/trade')

import numpy as np
import pandas as pd
import random

import MetaTrader5 as mt5
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
from dateutil import tz
from mt5_trade import PositionInfo
from common import Columns, Signal, Indicators, UP, DOWN
from technical import MA, ATR, ADX, SUPERTREND, POLARITY, TREND_ADX_DI
from time_utils import TimeUtils
from utils import Utils
from candle_chart import *

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

class PositionInfoSim(PositionInfo):
            
    def losscut(self, index, time, hi, lo, cl):
        # losscut 
        profit0 = cl - self.entry_price
        profit1 = hi - self.entry_price
        profit2 = lo- self.entry_price
        if self.signal() == Signal.SHORT:
            profit0 *= -1
            profit1 *= -1
            profit2 *= -1
        profits = [profit0, profit1, profit2]
        if np.min(profits) < - self.sl:
            self.losscutted = True
            #print('<Losscut>',  'Signal', self.signal(), index, time,'Profit', np.min(profits))
            if self.signal == Signal.SHORT:
                self.close(index, time, hi)
            else:
                self.close(index, time, lo)
                
    def trail(self, trailing_stop, index, time, cl):
        if trailing_stop == 0:
            return
        profit, profit_max = self.update_profit(cl, trailing_stop)
        if profit_max is None:
            return
        if (profit_max - profit) > trailing_stop:
            self.close(index, time, cl)
            self.trailing_stopped = True
            #print('<Trailing Close>', 'Signal', self.signal(), index, time, 'price', cl, 'profit', profit)
            return
    
    def close(self, index, time, price):
        self.exit_index = index
        self.exit_time = time
        self.exit_price = price
        profit = price - self.entry_price
        if self.signal() == Signal.SHORT:
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
            result.append([pos.signal, pos.entry_index, str(pos.entry_time), pos.entry_price, pos.exit_index, pos.exit_time, pos.exit_price, pos.profit])
        if num == 0:
            return (0, 0, 0, 0, 0)
        else:
            win_rate =  float(win) / float(num)
            if save:
                columns = ['Long/Short', 'entry_index', 'entry_time', 'entry_price', 'exit_index', 'exit_time', 'exit_price', 'profit']
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
        hi = data[Columns.HIGH]
        lo = data[Columns.LOW]
        cl = data[Columns.CLOSE]
        self.position_update(self.current, time[self.current], hi[self.current], lo[self.current], cl[self.current])
        sig = self.detect_entry(data)
        if sig == Signal.LONG or sig == Signal.SHORT:
            if self.trade_param['trailing_stop'] == 0:
                self.close_all_positions(self.current, time[self.current], cl[self.current])
            #print('<Signal>', sig, self.current, time[self.current])
            if self.trade_param['position_max'] > PositionInfoSim.position_num(self.positions):
                self.entry(data, self.current, sig)
        self.current += 1
        return True
    
    def position_update(self, index, time, hi, lo, cl):
        for pos in self.positions:
            if pos.closed:
                continue
            pos.losscut(index, time, hi, lo, cl)
        
        trailing_stop = self.trade_param['trailing_stop']
        if trailing_stop == 0:
            return
        for pos in self.positions:
            if pos.closed:
                continue
            pos.trail(trailing_stop, index, time, cl)
    
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
        sl = self.trade_param['sl']
        volume = self.trade_param['volume']
        if signal == Signal.LONG:
            typ = mt5.ORDER_TYPE_BUY
        else:
            typ = mt5.ORDER_TYPE_SELL
        pos = PositionInfoSim(self.symbol, typ, index, time[index], volume, 0, price, sl, 0)        
        #print('<Entry>', 'Signal', signal, index, time[index], 'price', price, 'sl', sl)
        self.positions.append(pos)
        
    def close_all_positions(self, index, time, price):
        for position in self.positions:
            if position.closed:
                continue
            position.close(index, time, price)
        
        
def pickup_trade(trades, tbegin, tend):
    out = []
    for trade in trades:
        if trade.entry_time >= tbegin and trade.entry_time <= tend:
            out.append(trade)
    return out

def plot(data: dict, trades):
    fig, axes = gridFig([5, 1], (20, 10))
    chart1 = CandleChart(fig, axes[0])
    chart1.drawCandle(data[Columns.TIME], data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])
    #name = 'MA' + str(params['MA']['window'])
    #chart.drawLine(data[Columns.TIME], data[name], color='blue')
    chart1.drawLine(data[Columns.TIME], data[Indicators.SUPERTREND_UPPER], color='red', linewidth=2.0)
    chart1.drawLine(data[Columns.TIME], data[Indicators.SUPERTREND_LOWER], color='green', linewidth=2.0)
    
    chart2 = CandleChart(fig, axes[1])
    chart2.drawLine(data[Columns.TIME], data[Indicators.SUPERTREND])
    
    for i, trade in enumerate(trades):
        trade.desc()
        if trade.signal() == Signal.LONG:
            marker = '^'
            color = 'green'
        else:
            marker = 'v'
            color = 'red'
        chart1.drawMarker(trade.entry_time, trade.entry_price, marker, color, overlay=i)
        
        if trade.losscutted:
            marker = 'x'
        elif trade.trailing_stopped:
            marker = '*'
        elif trade.time_upped:
            marker = 's'
        else:
            marker = 'o'
        if trade.profit is not None:
            if trade.profit < 0:
                color = 'gray'
        chart1.drawMarker(trade.exit_time, trade.exit_price, marker, color, overlay=i)            
    plt.show()
                
def plot_days(data, trades, days=7, is_start_monday=True):
    def next_monday(t: datetime):
        t1 = t
        while True:
            if t1.weekday() == 0:
                return t1
            t1 += timedelta(days=1)        
            return t1
    time = data[Columns.TIME]
    if is_start_monday:
        t = next_monday(time[0])
        t = datetime(t.year, t.month, t.day, tzinfo=JST)
    else:
        t = time[0]

    tend = time[-1]
    tend = datetime(tend.year, tend.month, tend.day, tzinfo=JST) + timedelta(days=1)
    while t < tend:
        t1 = t + timedelta(days=days)
        try:
            n, d = Utils.sliceBetween(data, time, t, t1)
            if n < 40:
                t += timedelta(days=days)
                continue
        except:
            t += timedelta(days=days)
            continue
        trds = pickup_trade(trades, t, t1)
        plot(d, trds)
        t += timedelta(days=days)        

def backtest(symbol, timeframe):
    loader = DataLoader()
    n = loader.load_data(symbol, timeframe, [2024], [1])
    technical_param = {'atr_window': 50, 'atr_multiply': 3.0, 'di_window': 25, 'adx_window': 25, 'polarity_window': 50}
    data = loader.data()
    indicators(data, technical_param)
    trade_param =  {'sl':100, 'trailing_stop': 150, 'volume': 0.1, 'position_max': 5, 'timelimit': 0}
    sim = TradeBotSim(symbol, timeframe, trade_param)
    sim.run(data, 150)
    while True:
        r = sim.update()
        if r == False:
            break
    trades = sim.positions
    (profit, num, profit_max, profit_min, win_rate) = PositionInfoSim.summary(trades)
    print(symbol, timeframe, 'profit', profit, 'drawdown', profit_min, 'num', num, )
    plot_days(data, trades)
    
def optimize_trade(symbol, timeframe, gene_space, years, months, number, repeat=30, save_every=False):
    loader = DataLoader()
    n = loader.load_data(symbol, timeframe, years, months)
    if n < 150:
        print('Data size small', n, symbol, timeframe, years[0], years[-1])
        return
    
    columns = ['symbol', 'timeframe', 'year_begin', 'year_end', 'atr_window', 'atr_multiply', 'sl', 'trailing_stop', 'profit', 'num', 'drawdown', 'fitness', 'win_rate']
    data0 = loader.data()
    technical = GeneticCode(gene_space[0])
    trade = GeneticCode(gene_space[1])
    result = []
    count = 0
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
            trade_param =  {'sl': sl, 'trailing_stop': trailing_stop, 'volume': 0.1, 'position_max': 100, 'timelimit': 0}
            sim = TradeBotSim(symbol, timeframe, trade_param)
            sim.run(data, 150)
            while True:
                r = sim.update()
                if r == False:
                    break
            trades = sim.positions
            (profit, num, profit_max, profit_min, win_rate) = PositionInfoSim.summary(trades)
            result.append([symbol, timeframe, years[0], years[-1], atr_window, atr_multiply, sl, trailing_stop, profit, num, profit_min, profit + profit_min, win_rate])
            count += 1
            print('#' + str(count), symbol, timeframe, 'profit', profit, 'drawdown', profit_min, 'num', num, 'win_rate', win_rate )    
            if save_every:
                df = pd.DataFrame(data=result, columns=columns)
                df = df.sort_values('fitness', ascending=False)
                try:
                    df.to_excel('./report/summary_' + symbol + '_' + timeframe + '_' + str(years[0]) + '-' + str(years[-1]) + '_' + str(number) + '.xlsx')
                except:
                    continue
    if save_every == False:
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
        optimize_trade(symbol, timeframe, gene_space, range(2020, 2024), range(1, 13), 0, repeat=10, save_every=True)
        print('Finish, Elapsed time', datetime.now() - t0, symbol, timeframe)

def main():
    args = sys.argv
    if len(args) < 2:
        #raise Exception('Bad parameter')
        # for debug
        args = ['', 'NIKKEI', 'H1']
        
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
    #backtest('NIKKEI', 'M15')