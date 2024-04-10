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
from technical import is_nan, is_nans, full, nans, VWAP, ATR, BB
from time_utils import TimeUtils, TimeFilter
from utils import Utils
from candle_chart import *

JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc')  

    
class Position:
    def __init__(self, trade_param, signal: Signal, index: int, time: datetime, price):
        self.sl = trade_param['sl']
        try:
            self.target = trade_param['target']
            self.trail_stop = trade_param['trail_stop']
        except:
            self.target = 0
            self.trail_stop = 0
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
        
        if self.target == 0:
            return False
        
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

    def indicators(self, param, vwap_begin_hour=7):
        VWAP(self.data, param['vwap_multiply'], begin_hour=vwap_begin_hour)
        ATR(self.data, 15, 100)
        BB(self.data, param['bb_window'], param['bb_ma_window'], param['bb_multiply'])        
        
    def run(self, technical_param: dict, trade_param: dict, time_filter: TimeFilter, begin: int):
        self.technical_param = technical_param
        self.trade_param = trade_param
        self.time_filter = time_filter
        self.indicators(technical_param) #, vwap_begin_hour=17)        
    
        current = begin
        trades = [] 
        while True:       
            position = self.detect_entry(current)
            if position is None:
               break
            self.trailing(position)
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
        vwap_cross = self.data[Indicators.VWAP_CROSS]
        bb_cross = self.data[Indicators.BB_CROSS]
        while begin > 0 and end > 0:
            for i in range(begin, end + 1):
                if vwap_cross[i] == UP:
                    pos = self.long(i)
                    return pos
                elif vwap_cross[i] == DOWN:
                    pos = self.short(i)
                    return pos 
            begin = self.begin_index(end + 1)
            end = self.end_index(begin + 1)               
        return None
    
    def trailing(self, position):
        begin = position.entry_index + 1
        end = self.end_index(begin + 1)
        typ = self.trade_param['exit_type']
        vwap_cross = self.data[Indicators.VWAP_CROSS]
        bb_cross = self.data[Indicators.BB_CROSS]
        for i in range(begin, end + 1):
            t = self.jst[i]
            if position.signal == Signal.LONG:
                if (typ == 0 and (vwap_cross[i] == DOWN or bb_cross[i] == DOWN)) or (typ == 1 and vwap_cross[i] == DOWN):
                    position.exit(i, self.jst[i], self.cl[i])
                    position.doten = True
                    return    
            elif position.signal == Signal.SHORT:
                if (typ == 0 and (vwap_cross[i] == UP or bb_cross[i] == UP)) or (typ == 1 and vwap_cross[i] == UP):
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
                    [GeneticCode.GeneInt,  10, 50,  10], # bb_window
                    [GeneticCode.GeneInt,  40, 100, 20],   # bb_ma_window
                    [GeneticCode.GeneFloat, 1.0, 4.0, 0.2], #bb_multiply
                    [GeneticCode.GeneFloat, 1.0, 4.0, 0.2] #vwap_multiply
                 ]
        technical_gen = GeneticCode(space)
        space = [
                    [GeneticCode.GeneFloat, 50, 400, 50],  # sl
                    [GeneticCode.GeneFloat, 50, 400, 50],  # target
                    [GeneticCode.GeneFloat, 20, 200, 20],   # trail_stop
                    [GeneticCode.GeneInt, 0, 1, 1],          #exit_type
                    [GeneticCode.GeneInt, 16, 22, 1],       # from_hour
                    [GeneticCode.GeneList, [0, 30]],        # from minute
                    [GeneticCode.GeneInt, 4, 20, 1]         # hours
                ]
        trade_gen = GeneticCode(space)
        return (technical_gen, trade_gen)

    def technical_code2param(self, code):
        names = ['bb_window', 'bb_ma_window', 'bb_multiply', 'vwap_multiply']
        param = {names[0]: code[0], names[1]: code[1], names[2]: code[2], names[3]: code[3]}
        return param, names

    def trade_code2param(self, code):
        names = ['sl', 'target', 'trail_stop', 'exit_type', 'from_hour', 'from_minute', 'hours']
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
            r = self.run(i, None, technical_param, trade_param)       
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
    
    def run(self, number, data_w1, technical_param, trade_param):
        sim = FastSimulator(self.data)
        self.timefilter = TimeFilter(JST, trade_param['from_hour'], trade_param['from_minute'], trade_param['hours'])
        trades = sim.run(technical_param, trade_param, self.timefilter, 100)
        if len(trades) == 0:
            return None
        df = Position.dataFrame(trades)
        df.to_excel(os.path.join(self.result_dir(), 'trade_summary_' + self.name +'.xlsx' ), index=False)
        r = Position.summary(trades)
        profit, acc, win_rate = r
        print('trade num:', len(trades), profit, win_rate)
        if profit < 0:
            return r
        fig, ax = makeFig(1, 1, (10, 5))
        if data_w1 is not None:
            chart = CandleChart(fig, ax, date_format=CandleChart.DATE_FORMAT_DAY)
            chart.drawCandle(data_w1[Columns.JST], data_w1[Columns.OPEN],data_w1[Columns.HIGH],data_w1[Columns.LOW],data_w1[Columns.CLOSE],)
            ax2 = ax.twinx()
        else:
            ax2 = ax
        chart2 = CandleChart(fig, ax2, date_format=CandleChart.DATE_FORMAT_DAY)
        chart2.drawScatter(acc[0], acc[1])
        chart2.drawLine(acc[0], acc[1])
        plt.savefig(os.path.join(self.chart_dir(), str(number) + '_profit_curve.png'))
        
        #plot_daily(self.symbol, self.timeframe, self.data, trades, self.chart_dir())
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
            path = os.path.join(save_dir, 'VWAP_' + symbol + '(' + timeframe + ')_' +  t.strftime('%Y-%m-%d') + '.png')
            plot(title, d, trds, path)
            count += 1
        t += timedelta(days=1)
        if t > jst[-1]:
            break
        t1 += timedelta(days=1)

def plot(title, data: dict, trades, save_path):
    fig, axes = gridFig([4, 1, 1, 1, 1], (15, 15))
    time = data[Columns.JST]
    high = max(data[Columns.HIGH])
    low = min(data[Columns.LOW])
    chart1 = CandleChart(fig, axes[0], title=title, date_format=CandleChart.DATE_FORMAT_DATE_TIME)
    chart1.drawCandle(time, data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])
    chart1.drawLine(time, data[Indicators.VWAP_UPPER], color='blue', linewidth=1.0)
    chart1.drawLine(time, data[Indicators.VWAP_LOWER], color='red', linewidth=1.0)
    chart1.drawLine(time, data[Indicators.VWAP], color='green', linewidth=1.0)
    chart1.drawLine(time, data[Indicators.BB_UPPER], color='blue', linestyle='dotted', linewidth=2.0)
    chart1.drawLine(time, data[Indicators.BB_LOWER], color='red', linestyle='dotted', linewidth=2.0)
    chart1.drawLine(time, data[Indicators.BB_MA], color='green', linewidth=2.0)
    #mark_signal(chart1, data, Columns.MID, data[Indicators.VWAP_CROSS_UP], 'v', 'green', 20)
    #mark_signal(chart1, data, Columns.MID, data[Indicators.VWAP_CROSS_DOWN], '^', 'red', 20)
    #mark_signal(chart1, data, Columns.MID, data[Indicators.BB_CROSS_UP], 'o', 'green', 20)
    #mark_signal(chart1, data, Columns.MID, data[Indicators.BB_CROSS_DOWN], 'o', 'red', 20)
    
    chart2 = CandleChart(fig, axes[1], write_time_range=True, date_format=CandleChart.DATE_FORMAT_DATE_TIME)
    chart2.drawLine(time, data[Indicators.ATR], color='blue')
    chart2.drawLine(time, data[Indicators.ATR_LONG], color='green', linewidth=2.0)
    
    chart3 = CandleChart(fig, axes[2], write_time_range=True, date_format=CandleChart.DATE_FORMAT_DATE_TIME)
    chart3.drawLine(time, data[Indicators.VWAP_UP], color='blue')
    chart3.drawLine(time, data[Indicators.VWAP_DOWN], color='red')
    
    chart4 = CandleChart(fig, axes[3], title = title, write_time_range=True, date_format=CandleChart.DATE_FORMAT_DATE_TIME)
    chart4.drawLine(time, data[Indicators.BB_UP], color='blue')
    chart4.drawLine(time, data[Indicators.BB_DOWN], color='red')
    
    
    plot_markers(chart1, trades, low, high)     
    if save_path is not None:
        plt.savefig(save_path)
    plt.close()
        
def mark_signal(chart, data, column, signal, marker, color, size):
    d = data[column]
    jst = data[Columns.JST]
    n = len(d)
    for i in range(n):
        if is_nan(signal[i]):
            continue
        chart.drawMarker(jst[i], d[i], marker=marker, color=color, markersize=size)

def plot_markers(chart, trades, low, high):
    for i, trade in enumerate(trades):
        if trade.signal == Signal.LONG:
            marker = '^'
            color = 'green'
        else:
            marker = 'v'
            color = 'red'
        chart.drawMarker(trade.entry_time, trade.entry_price, marker, color, markersize=20.0)
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
            chart.drawMarker(trade.exit_time, trade.exit_price - (high - low) / 10, marker, 'gray', markersize=20.0)            
            chart.drawMarker(trade.exit_time, y, '$' + str(i) + '$', color, markersize=20.0, alpha=0.3)   

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
    if s < 0:
        return
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
        
def simulate(name):
    shutil.rmtree('./chart/')
    os.makedirs('./chart/')
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
    handler.load_data(2024, 4, 2024, 4)
    technical_param = {'bb_window':50, 'bb_ma_window':40, 'bb_multiply': 4.0, 'vwap_multiply': 1.0}
    trade_param = {'sl': 250, 'target': 300, 'trail_stop': 20, 'exit_type': 0, 'volume': 0.1, 'position_max': 5, 'timelimit': 1}
    timefilter = TimeFilter(JST, 10, 0, 12)
    loader = DataLoader()
    #n, data_w1 = loader.load_data(symbol, 'W1', 2024, 4, 2024, 4)
    handler.run(1, None, technical_param, trade_param)
    
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
    handler.load_data(2019, 1, 2024, 5)
    handler.optimize(repeat=200) 

def analyze(name) :
    symbol = 'NIKKEI'
    timeframe = 'M1'
    loader = DataLoader()
    n, data1 = loader.load_data(symbol, timeframe, 2024, 4, 2024, 4)
    handler = Handler(name, symbol, timeframe)
    technical_param = {'bb_window':50, 'bb_ma_window':40, 'bb_multiply': 4.0, 'vwap_multiply': 1.0}
    trade_param = {'sl': 250, 'target': 300, 'trail_stop': 20, 'exit_type': 0, 'volume': 0.1, 'position_max': 5, 'timelimit': 1}
    timefilter = TimeFilter(JST, 10, 0, 12)
    sim = FastSimulator(data1)
    sim.indicators(technical_param)
    #df = Position.dataFrame(trades)
    #df.to_excel(os.path.join(handler.result_dir(), 'dow_trades.xlsx'))
     
    #n, data2 = loader.load_data(symbol, 'W1', 2019, 1, 2024, 3)
    #save_path = os.path.join(handler.chart_dir(), 'dow_profit_curve_W1.png')
    #plot_profit('DOW Profit Curve (2019-2024)', save_path, data2, trades)
    
    #n, data3 = loader.load_data(symbol, 'D1', 2019, 1, 2024, 3)
    #plot_profit_monthly(handler.chart_dir(), data3, trades)     
    
    plot_daily(symbol, timeframe, data1, [], handler.chart_dir())
    
    pass
    
def debug():
    symbol = 'NIKKEI'
    timeframe = 'M1'
    loader = DataLoader()
    n, data1 = loader.load_data(symbol, timeframe, 2024, 4, 2024, 4)
    handler = Handler('', symbol, timeframe)
    technical_param = {'bb_window':50, 'bb_ma_window':40, 'bb_multiply': 4.0, 'vwap_multiply': 1.0}
    trade_param = {'sl': 250, 'target': 300, 'trail_stop': 20, 'exit_type': 0, 'volume': 0.1, 'position_max': 5, 'timelimit': 1}
    timefilter = TimeFilter(JST, 10, 0, 12)
    sim = FastSimulator(data1)
    sim.indicators(technical_param)
    df = pd.DataFrame(sim.data)
    df = df.iloc[-500:]
    os.mkdir('./debug/')
    df.to_csv('./debug/nikkei_04-10.csv', index=False)
    
    
               
if __name__ == '__main__':
    debug()
    #optimize('vwap_opt_nikkei_from17_#2')
    #analyze('vwap_ana_nikkei_2024-4')
    #simulate('vwap_sim_nikkei_2024-4')