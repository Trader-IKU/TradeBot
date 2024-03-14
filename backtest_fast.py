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
from technical import is_nan, is_nans, ATR_TRAIL, full, nans, STDEV, BBRATE, pivot, zero_cross, slope
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
        bb_window = param['bb_window']
        ma_window = param['ma_window']   
        BBRATE(self.data, bb_window, ma_window)
        bb_pivot_left = param['bb_pivot_left']
        bb_pivot_right = param['bb_pivot_right']
        bb_pivot_threshold = param['bb_pivot_threshold']
        hi, lo, _ = pivot(self.data[Indicators.BBRATE], bb_pivot_left, bb_pivot_right, bb_pivot_threshold)
        self.data['PIVOTH'] = hi
        self.data['PIVOTL'] = lo
        up, down = zero_cross(self.data[Indicators.BBRATE])
        self.data['CROSS_UP'] = up
        self.data['CROSS_DOWN'] = down
        slp = slope(self.data[Columns.CLOSE], 10)
        self.data['SLOPE'] = slp

    def run(self, technical_param: dict, trade_param: dict, time_filter: TimeFilter, begin: int):
        self.technical_param = technical_param
        self.trade_param = trade_param
        self.time_filter = time_filter
        self.indicators(technical_param)        
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
                    [GeneticCode.GeneInt, 0, 1, 1]          #doten
                ]
        trade_gen = GeneticCode(space)
        return (technical_gen, trade_gen)

    def technical_code2param(self, code):
        names = ['bb_window', 'ma_window', 'bb_pivot_threshold', 'bb_pivot_left', 'bb_pivot_right']
        param = {names[0]: code[0], names[1]: code[1], names[2]: code[2], names[3]: 3, names[4]:3}
        return param, names

    def trade_code2param(self, code):
        names = ['sl', 'target', 'trail_stop', 'doten']
        param = {names[0]: code[0], names[1]: code[1], names[2]: code[2], names[3]: code[3]}
        return param, names

    def optimize(self, from_hour, from_minute, hours, repeat=100):
        spaces = self.gene_space()
        result = []
        for i in range(repeat):
            code = spaces[0].create_code()
            technical_param, technical_names = self.technical_code2param(code)
            code = spaces[1].create_code()
            trade_param, trade_names = self.trade_code2param(code)
            r = self.run(i, technical_param, trade_param, from_hour, from_minute, hours)       
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
    
    def run(self, number, technical_param, trade_param, from_hour, from_minute, hours):
        sim = FastSimulator(self.data)
        self.timefilter = TimeFilter(JST, from_hour, from_minute, hours)
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
        
        
    def plot_day(self, trades):
        jst = self.data[Columns.JST]
        tend = jst[-1]
        t = datetime(jst[0].year, jst[0].month, jst[0].day, self.timefilter.begin_hour, self.timefilter.begin_minute)
        t0 = t.replace(tzinfo=JST)
        t1 = t0 + timedelta(hours=self.timefilter.hours)
        count = 1
        while t0 < tend:
            n, d = Utils.sliceBetween(self.data, jst, t0, t1)
            if n > 20:
                trds = self.pickup_trade(trades, t0, t1)
                plot(self.symbol, self.timeframe, d, trds, chart_num=count)
                count += 1
            t0 += timedelta(days=1)
            t1 = t0 + timedelta(hours=self.timefilter.hours)
        
        
        
    def pickup_trade(self, trades, tbegin, tend):
        out = []
        for trade in trades:
            if trade.entry_time >= tbegin and trade.entry_time <= tend:
                out.append(trade)
            elif trade.exit_time >= tbegin and trade.exit_time <= tend:
                out.append(trade)
        return out        
        
def plot(symbol, timeframe, data: dict, trades, chart_num=0):
    fig, axes = gridFig([2, 1], (15, 10))
    time = data[Columns.JST]
    title = symbol + '(' + timeframe + ')  ' + str(time[0]) + '...' + str(time[-1]) 
    chart1 = CandleChart(fig, axes[0], title=title, date_format=CandleChart.DATE_FORMAT_DATE_TIME)
    chart1.drawCandle(time, data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])
    #chart1.drawLine(time, data[Indicators.STDEV_UPPER], color='blue', linestyle='dotted', linewidth=1.0)
    chart2 = CandleChart(fig, axes[1], title = title, write_time_range=True, date_format=CandleChart.DATE_FORMAT_DATE_TIME)
    chart2.drawLine(time, data[Indicators.BBRATE])
    chart2.ylimit([-400, 400])
    chart2.drawScatter(time, data['PIVOTH'], color='green')
    chart2.drawScatter(time, data['PIVOTL'], color='orange')
    #chart2.drawScatter(time, data['CROSS_UP'], color='blue')
    #chart2.drawScatter(time, data['CROSS_DOWN'], color='gray')
    #chart3 = CandleChart(fig, axes[2], write_time_range=True, date_format=CandleChart.DATE_FORMAT_DATE_TIME)
    #chart3.drawLine(time, data['SLOPE'])

    high = max(data[Columns.HIGH])
    low = min(data[Columns.LOW])
    for i, trade in enumerate(trades):
        if trade.signal == Signal.LONG:
            marker = '^'
            color = 'green'
        else:
            marker = 'v'
            color = 'red'
        chart1.drawMarker(trade.entry_time, trade.entry_price, marker, color, markersize=20.0)
        
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
            chart1.drawMarker(trade.exit_time, trade.exit_price - (high - low) / 10, marker, 'gray', markersize=20.0)            
            chart1.drawMarker(trade.exit_time, y, '$' + str(i) + '$', color, markersize=15.0, alpha=0.9)            
    plt.savefig(os.path.join(self.chart_dir(), str(chart_num) + '.png'))

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
        args = ['', 'DOW', 'M1']
    if len(args) < 4:
        number = 0
    else:
        number = int(args[3])        
    symbol = args[1].upper()
    timeframe = args[2].upper()
    handler = Handler(name, symbol, timeframe)
    handler.load_data(2017, 9, 2024, 3)
    handler.optimize(22, 0, 4, repeat=100) 
       
    

               
if __name__ == '__main__':

    optimize('STDEV_COUNTER')
    
    #backtest('NIKKEI', 'M15')