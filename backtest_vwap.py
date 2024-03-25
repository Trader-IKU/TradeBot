import os
import shutil
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
from backtest import DataLoader, GeneticCode, PositionInfoSim
from technical import is_nan, is_nans, full, nans, VWAP
from time_utils import TimeUtils, TimeFilter
from utils import Utils
from candle_chart import *

JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc')  

    
class Position:
    def __init__(self, trade_param, signal: Signal, index: int, time: datetime, price):
        self.sl = trade_param['sl']
        self.target = trade_param['target']
        self.trail_stop = trade_param['trail_stop']
        self.signal = signal
        self.entry_index = index
        self.entry_time = time
        self.entry_price = price
        self.exit_index = None
        self.exit_time = None       
        self.exit_price = None
        self.profit = None
        self.fired = False
        self.profit_max = None
        self.closed = False
        self.losscutted = False
        self.trail_stopped = False
        self.doten = False
        self.timelimit = False
        
    # return  True: Closed,  False: Not Closed
    def update(self, index, time, o, h, l, c):
        # check stoploss
        if self.signal == Signal.LONG:
            profit = l - self.entry_price
            if profit <= -1 * self.sl:
                 self.exit(index, time, l)
                 self.losscutted = True
                 return True
            profit = c - self.entry_price
        else:
            profit = self.entry_price - h
            if profit <= -1 * self.sl:
                self.exit(index, time, h)
                self.losscutted = True
                return True
            profit = c - self.entry_price            
        
        if self.fired:
            if profit > self.profit_max:
                self.profit_max = profit
            else:
                if self.profit_max - profit < self.trail_stop:
                    self.exit(index, time, c)
                    self.trail_stopped = True         
                    return True
        else:
            if profit >= self.target:
                self.profit_max = profit
                self.fired = True        
        return False
    
    def exit(self, index, time, price):
        self.exit_index = index
        self.exit_time = time
        self.exit_price = price
        self.closed = True
        self.profit = price - self.entry_price
        if self.signal == Signal.SHORT:
            self.profit *= -1
        
        
    @staticmethod
    def summary(positions):
        s = 0
        win = 0
        profits = []
        acc = []
        time = []
        for position in positions:
            profits.append(position.profit)
            s += position.profit
            time.append(position.entry_time)
            acc.append(s)
            if position.profit > 0:
                win += 1
        if len(positions) > 0:
            win_rate = float(win) / float(len(positions))
        else:
            win_rate = 0
        return s, (time, acc), win_rate
    
    @staticmethod
    def dataFrame(positions):
        data = []
        for i, position in enumerate(positions):
            d = [i, position.signal, position.entry_index, str(position.entry_time), position.entry_price]
            d += [position.exit_index, str(position.exit_time), position.exit_price, position.profit]
            d += [position.closed, position.losscutted,  position.trail_stopped, position.doten, position.timelimit]
            data.append(d)
        columns = ['No', 'signal', 'entry_index', 'entry_time', 'entry_price']
        columns += ['exit_index', 'exit_time', 'exit_price', 'profit']
        columns += ['closed', 'losscuted', 'trail_stopped', 'doten', 'timelimit']
        df = pd.DataFrame(data=data, columns=columns)
        return df 

class FastSimulator:
            
    def __init__(self, data: dict):
        self.data = data
        self.size = len(data[Columns.TIME])
        self.jst = self.data[Columns.JST]
        self.op = self.data[Columns.OPEN]
        self.hi = self.data[Columns.HIGH]
        self.lo = self.data[Columns.LOW]
        self.cl = self.data[Columns.CLOSE]

    def indicators(self, param):
        VWAP(self.data, 1.28)
        
    def run(self, technical_param: dict, trade_param: dict, time_filter: TimeFilter, begin: int):
        self.technical_param = technical_param
        self.trade_param = trade_param
        self.time_filter = time_filter
        self.indicators(technical_param)        
        return []
    
    
        current = begin
        trades = [] 
        while True:       
            position = self.detect_entry(current)
            if position is None:
               break
            self.trail(position)
            if position.closed:
                trades.append(position)
                current = position.exit_index
            else:
                raise Exception('Position was not closed')
        return trades
    
    def begin_index(self, index):
        while index < self.size : 
            t = self.jst[index]
            if self.time_filter.on(t):
                return index
            index += 1
        return -1
    
    def end_index(self, index):
        while index < self.size : 
            t = self.jst[index]
            if not self.time_filter.on(t):
                return index - 1
            index += 1
        return -1
    
    def detect_entry(self, index):
        begin = self.begin_index(index)
        end = self.end_index(begin + 1)
        while begin > 0 and end > 0:
            for i in range(begin, end + 1):
                pivot = self.detect_pivot(i)
                if pivot == 1:
                    pos = self.short(i)
                    return pos
                elif pivot == -1:
                    pos = self.long(i)
                    return pos 
            begin = self.begin_index(end + 1)
            end = self.end_index(begin + 1)               
        return None
    
    def trail(self, position):
        begin = position.entry_index + 1
        end = self.end_index(begin + 1)
        for i in range(begin, end + 1):
            t = self.jst[i]
            if self.trade_param['doten'] > 0:
                # check doten
                pivot = self.detect_pivot(i)
                if (position.signal == Signal.LONG and pivot == 1) or (position.signal == Signal.SHORT and pivot == -1):
                    position.exit(i, self.jst[i], self.cl[i])
                    position.doten = True
                    return
            if position.update(i, t, self.op[i], self.hi[i], self.lo[i], self.cl[i]):
                # closed
                return            
        # time limit close
        position.exit(end, self.jst[end], self.cl[end])
        position.timelimit = True
        return
    
    def detect_pivot(self, index):
        pivot_h = self.data['PIVOTH']
        pivot_l = self.data['PIVOTL']
        pivot_right = self.technical_param['bb_pivot_right']
        if is_nan(pivot_h[index - pivot_right]) == False:
            return 1
        if is_nan(pivot_l[index - pivot_right]) == False:
            return -1
        return 0
    
    def long(self, index):
        position = Position(self.trade_param, Signal.LONG, index, self.jst[index], self.cl[index])
        return position        
        
    def short(self, index):
        position = Position(self.trade_param, Signal.SHORT, index, self.jst[index], self.cl[index])
        return position     

class Handler:
    
    def __init__(self, name, symbol, timeframe):
        self.name = name
        self.symbol = symbol
        self.timeframe = timeframe
        self.result_dir(create=True)
        self.chart_dir(create=True)
        self.data = None
 
    def result_dir(self, create=False):     
        dir = os.path.join('./result/', self.name)
        if create:
            os.makedirs(dir, exist_ok=True)
        return dir        
    
    def chart_dir(self, create=False):     
        dir = os.path.join('./chart/', self.name)
        if create:
            os.makedirs(dir, exist_ok=True)
        return dir        
   
    def load_data(self, from_year, from_month, to_year, to_month):
        loader = DataLoader()
        n, data = loader.load_data(self.symbol, self.timeframe, from_year, from_month, to_year, to_month)
        if n < 200:
            raise Exception('Data size is too small')           
        self.data = data     
        return data   

    def gene_space(self):
        space = [
                    [GeneticCode.GeneInt,  5, 40,  5], # bb_window
                    [GeneticCode.GeneInt, 5, 40, 5],   # ma_window
                    [GeneticCode.GeneFloat, 150, 400, 50] #bb_pivot_threshold
                 ]
        technical_gen = GeneticCode(space)
        space = [
                    [GeneticCode.GeneFloat, 50, 400, 50],  # sl
                    [GeneticCode.GeneFloat, 50, 400, 50],  # target
                    [GeneticCode.GeneFloat, 20, 200, 20],   # trail_stop
                    [GeneticCode.GeneInt, 0, 1, 1],          #doten
                    [GeneticCode.GeneInt, 8, 10, 1],       # from_hour
                    [GeneticCode.GeneList, [0, 30]],        # from minute
                    [GeneticCode.GeneInt, 2, 8, 1]         # hours
                ]
        trade_gen = GeneticCode(space)
        return (technical_gen, trade_gen)

    def technical_code2param(self, code):
        names = ['bb_window', 'ma_window', 'bb_pivot_threshold', 'bb_pivot_left', 'bb_pivot_right']
        param = {names[0]: code[0], names[1]: code[1], names[2]: code[2], names[3]: 3, names[4]:3}
        return param, names

    def trade_code2param(self, code):
        names = ['sl', 'target', 'trail_stop', 'doten', 'from_hour', 'from_minute', 'hours']
        param = {names[0]: code[0], names[1]: code[1], names[2]: code[2], names[3]: code[3], names[4]: code[4], names[5]: code[5], names[6]: code[6]}
        return param, names

    def optimize(self, repeat=100):
        spaces = self.gene_space()
        result = []
        for i in range(repeat):
            code = spaces[0].create_code()
            technical_param, technical_names = self.technical_code2param(code)
            code = spaces[1].create_code()
            trade_param, trade_names = self.trade_code2param(code)
            r = self.run(i, technical_param, trade_param)       
            if r is None:
                continue 
            s, acc, win_rate = r
            drawdown = np.min(acc[1])
            d = [i] + list(technical_param.values()) + list(trade_param.values()) + [s, drawdown, win_rate]
            result.append(d)
            columns = ['number'] + technical_names + trade_names + ['profit', 'drawdonw', 'win_rate']
            df = pd.DataFrame(data=result, columns=columns)
            df = df.sort_values('profit', ascending=False)        
            try:
                df.to_excel(os.path.join(self.result_dir(), 'Summary_' + self.name + '.xlsx'), index=False)
            except:
                pass   
        return df
    
    def run(self, number, technical_param, trade_param):
        sim = FastSimulator(self.data)
        self.timefilter = TimeFilter(JST, trade_param['from_hour'], trade_param['from_minute'], trade_param['hours'])
        trades = sim.run(technical_param, trade_param, self.timefilter, 100)
        if len(trades) == 0:
            return None
        r = Position.summary(trades)
        s, acc, win_rate = r
        fig, ax = makeFig(1, 1, (10, 5))
        chart = CandleChart(fig, ax, date_format=CandleChart.DATE_FORMAT_DAY)
        chart.drawScatter(acc[0], acc[1])
        chart.drawLine(acc[0], acc[1])
        plt.savefig(os.path.join(self.chart_dir(), str(number) + '_profit_curve.png'))
        print('trade num:', len(trades), s, win_rate)
        #self.plot_day(trades)
        return r
        
def plot_weekly(symbol, timeframe, data: dict, trades, save_dir):
    def next_monday(time, begin):
        n = len(time)
        if begin >= n:
            return -1
        i = begin
        w = time[i].weekday()
        while True:
            if i >= n:
                return -1
            if w != time[i].weekday():
                break
            i += 1
            
        while True:
            if i >= n:
                return -1 
            if time[i].weekday() == 0:
                return i
            i += 1
        return n

    jst = data[Columns.JST]
    i0 = 0
    i1 = next_monday(jst, i0 + 1)
    count = 1
    while i1 >0:
        d = Utils.sliceDict(data, i0, i1 - 1)    
        trds = pickup_trade(trades, jst[i0], jst[i1 - 1])
        title = 'Trade#' + str(count) + ' ' +  symbol + '(' + timeframe + ') ' + jst[i0].strftime('%Y/%m/%d')
        path = os.path.join(save_dir, 'No' + str(count) + '_' + symbol + '(' + timeframe + ')_trade.png')
        plot(title, d, trds, path)
        count += 1
        i0 = i1
        i1 = next_monday(jst, i0 + 1)

def plot_daily(symbol, timeframe, data: dict, trades, save_dir):
    jst = data[Columns.JST]
    t  = jst[0]
    t = tjst(t.year, t.month, t.day, hour=8)
    t1 = t + timedelta(hours=22)
    count = 1
    while True:
        n, d = Utils.sliceBetween(data, jst, t, t1)
        if n > 20:    
            trds = pickup_trade(trades, t, t1)
            title = 'Trade#' + str(count) + ' ' +  symbol + '(' + timeframe + ') ' + t.strftime('%Y/%m/%d')
            path = os.path.join(save_dir, 'No' + str(count) + '_' + symbol + '(' + timeframe + ')_trade.png')
            plot(title, d, trds, path)
            count += 1
        t += timedelta(days=1)
        if t > jst[-1]:
            break
        t1 += timedelta(days=1)

def plot(title, data: dict, trades, save_path):
    fig, axes = gridFig([2, 1, 1], (15, 10))
    time = data[Columns.JST]
    high = max(data[Columns.HIGH])
    low = min(data[Columns.LOW])
    chart1 = CandleChart(fig, axes[0], title=title, date_format=CandleChart.DATE_FORMAT_DATE_TIME)
    chart1.drawCandle(time, data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])
    chart1.drawLine(time, data[Indicators.VWAP_UPPER], color='blue', linewidth=1.0)
    chart1.drawLine(time, data[Indicators.VWAP_LOWER], color='red', linewidth=1.0)
    chart1.drawLine(time, data[Indicators.VWAP], color='green', linewidth=1.0)
    chart2 = CandleChart(fig, axes[1], title = title, write_time_range=True, date_format=CandleChart.DATE_FORMAT_DATE_TIME)
    chart2.drawLine(time, data[Indicators.VWAP_STD])
    #chart2.ylimit([-400, 400])
    #chart2.drawScatter(time, data['PIVOTH'], color='green')
    #chart2.drawScatter(time, data['PIVOTL'], color='orange')
    #chart2.drawScatter(time, data['CROSS_UP'], color='blue')
    #chart2.drawScatter(time, data['CROSS_DOWN'], color='gray')
    chart3 = CandleChart(fig, axes[2], write_time_range=True, date_format=CandleChart.DATE_FORMAT_DATE_TIME)
    chart3.drawLine(time, data[Indicators.VWAP_SLOPE])
    chart3.ylimit([-10, 10])
    #plot_markers(chart1, trades, low, high)     
    if save_path is not None:
        plt.savefig(save_path)

def plot_markers(chart, trades, low, high):
    for i, trade in enumerate(trades):
        if trade.signal == Signal.LONG:
            marker = '^'
            color = 'green'
        else:
            marker = 'v'
            color = 'red'
        chart.drawMarker(trade.entry_time, trade.entry_price, marker, color, markersize=10.0)
        if trade.losscutted:
            marker = 'x'
        elif trade.doten:
            marker = '*'
        elif trade.trail_stopped:
            marker = 'o'
        elif trade.timelimit:
            marker = '>'
        if trade.signal == Signal.LONG:
            color = 'green'
            y = high
        else:
            color = 'red'
            y = low
        if trade.profit < 0:
            color = 'black'
        if trade.exit_price is not None:
            chart.drawMarker(trade.exit_time, trade.exit_price - (high - low) / 10, marker, 'gray', markersize=10.0)            
            chart.drawMarker(trade.exit_time, y, '$' + str(i) + '$', color, markersize=10.0, alpha=0.9)   

def pickup_trade(trades, tbegin, tend):
    out = []
    for trade in trades:
        if trade.entry_time >= tbegin and trade.entry_time <= tend:
            out.append(trade)
        elif trade.exit_time >= tbegin and trade.exit_time <= tend:
            out.append(trade)
    return out        
    
def plot_profit(title, save_path, candle, trades):
    r = Position.summary(trades)
    s, acc, win_rate = r
    print('trade num:', len(trades), s, win_rate)
    fig, ax = makeFig(1, 1, (20, 10))
    chart1 = CandleChart(fig, ax, title=title, date_format=CandleChart.DATE_FORMAT_YEAR_MONTH)
    chart1.drawCandle(candle[Columns.TIME], candle[Columns.OPEN], candle[Columns.HIGH], candle[Columns.LOW], candle[Columns.CLOSE])
    ax2 = ax.twinx()
    chart2 = CandleChart(fig, ax2, title=title, date_format=CandleChart.DATE_FORMAT_YEAR_MONTH)
    chart2.drawLine(acc[0], acc[1], color='green', linewidth=1.0)
    chart2.drawScatter(acc[0], acc[1], color='red', size=20)
    if save_path is not None:
        plt.savefig(save_path)

def tjst(year, month, day, hour=0):
    t0 = datetime(year, month, day, hour)
    t = t0.replace(tzinfo=JST)
    return t

def plus_half_year(year, month):
    month += 6
    if month > 12:
        year += 1
        month = 1
    t = tjst(year, month, 1)
    t -= timedelta(days=1)
    return (t, year, month)

def plot_profit_monthly(dir, candle, trades):
    year = 2019
    month = 1
    tend = tjst(2024, 3, 10)
    count = 1
    t = tjst(year, month, 1)
    while t < tend:
        t = tjst(year, month, 1)
        t1, year, month = plus_half_year(year, month)
        n, d = Utils.sliceBetween(candle, candle[Columns.JST], t, t1)
        if n > 0:
            trds = pickup_trade(trades, t, t1)
            path = os.path.join(dir, 'profit_' + str(year) + '-' + str(month) + '.png')
            title = 'DOW Profit Curve #' + str(count) + '  ' + str(year)
            plot_profit(title, path, d, trds)
        count += 1
        
def main(name):
    shutil.rmtree('./chart/')
    os.makedirs('./chart/')
    args = sys.argv
    if len(args) < 2:
        args = ['', 'DOW', 'M1']
    if len(args) < 4:
        number = 0
    else:
        number = int(args[3])
        
    symbol = args[1].upper()
    timeframe = args[2].upper()
    handler = Handler(name, symbol, timeframe)
    handler.load_data(2024, 2, 2024, 2)
    technical_param = {'bb_window':15, 'ma_window':15, 'bb_pivot_left': 10, 'bb_pivot_right':3, 'bb_pivot_threshold': 200}
    trade_param = {'sl': 200, 'target': 150, 'trail_stop': 50, 'doten': 1}
    handler.run(1, technical_param, trade_param, 22, 0, 4)
    
def optimize(name):
    args = sys.argv
    if len(args) < 2:
        args = ['', 'NIKKEI', 'M1']
    if len(args) < 4:
        number = 0
    else:
        number = int(args[3])        
    symbol = args[1].upper()
    timeframe = args[2].upper()
    handler = Handler(name, symbol, timeframe)
    handler.load_data(2019, 1, 2024, 3)
    handler.optimize(repeat=500) 

def analyze(name) :
    symbol = 'DOW'
    timeframe = 'M1'
    loader = DataLoader()
    n, data1 = loader.load_data(symbol, timeframe, 2024, 3, 2024, 3)
    handler = Handler(name, symbol, timeframe)
    technical_param = {}
    trade_param = {'sl': 250, 'target': 300, 'trail_stop': 20, 'doten': 0}
    sim = FastSimulator(data1)
    timefilter = TimeFilter(JST, 20, 0, 6)
    trades = sim.run(technical_param, trade_param, timefilter, 24 * 60)
    #df = Position.dataFrame(trades)
    #df.to_excel(os.path.join(handler.result_dir(), 'dow_trades.xlsx'))
     
    #n, data2 = loader.load_data(symbol, 'W1', 2019, 1, 2024, 3)
    #save_path = os.path.join(handler.chart_dir(), 'dow_profit_curve_W1.png')
    #plot_profit('DOW Profit Curve (2019-2024)', save_path, data2, trades)
    
    #n, data3 = loader.load_data(symbol, 'D1', 2019, 1, 2024, 3)
    #plot_profit_monthly(handler.chart_dir(), data3, trades)     
    
    plot_daily(symbol, timeframe, data1, trades, handler.chart_dir())
    
    pass
    

               
if __name__ == '__main__':

    #optimize('vwap_optimize_dow#1')
    
    analyze('vwap_ana_dow#1')