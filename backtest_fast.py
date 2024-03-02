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
from technical import ATR_TRAIL, full, nans
from time_utils import TimeUtils, TimeFilter
from utils import Utils
from candle_chart import *

JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc')  


def indicators(data: dict, param: dict):
    atr_window = param['atr_window']
    atr_multiply = param['atr_multiply']
    peak_hold_term = param['peak_hold_term']
    ATR_TRAIL(data, atr_window, atr_multiply, peak_hold_term)
    
    
class Position:
    def __init__(self, signal: Signal, index: int, time: datetime, price):
        self.signal = signal
        self.entry_index = index
        self.entry_time = time
        self.entry_price = price
        self.exit_index = None
        self.exit_time = None       
        self.exit_price = None
        self.profit = None
        self.losscutted = False
        
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
            
    def __init__(self, trade_param):
        self.trade_param = trade_param

    def run(self, data):
        d = data[Indicators.ATR_TRAIL_TREND]
        detect_count = self.trade_param['detect_count']
        signal = self.detect(d, detect_count)
        trades = self.trading(data, signal)
        return trades
    
    def detect(self, data, detect_count):
        n = len(data)
        signal = nans(n)
        long_pattern = full(DOWN, detect_count) + full(UP, detect_count)
        short_pattern = full(UP, detect_count) + full(DOWN, detect_count)
        count = 0
        for i in range(detect_count * 2 - 1, n):
            d = data[i - detect_count * 2 + 1: i + 1]
            if d == long_pattern:
                signal[i] = Signal.LONG        
                count += 1
            if d == short_pattern:
                signal[i] = Signal.SHORT
                count += 1
        #print('signal count:', count)
        return signal

    def trading(self, data, signal):
        losscut = self.trade_param['sl']
        time = data[Columns.JST]
        cl = data[Columns.CLOSE]
        hi = data[Columns.HIGH]
        lo = data[Columns.LOW]
        n = len(signal)
        
        ibefore = None
        sigbefore = None
        trades = []
        for i in range(n):
            sig = signal[i]
            if ibefore is None:
                if sig == Signal.LONG or sig == Signal.SHORT:
                    ibefore = i
                    sigbefore = sig
                else:
                    continue
            else:
                if sigbefore == Signal.LONG and sig == Signal.SHORT:
                    trade = self.long(time, cl, lo, hi, losscut, ibefore, i)                          
                    trades.append(trade)
                    ibefore = i
                    sigbefore = sig
                elif sigbefore == Signal.SHORT and sig == Signal.LONG:
                    trade = self.short(time, cl, lo, hi, losscut, ibefore, i)                          
                    trades.append(trade)
                    ibefore = i
                    sigbefore = sig

        #print(len(trades))
        return trades
    
    def long(self, time, cl, lo, hi, losscut, begin, end):
        position = Position(Signal.LONG, begin, time[begin], cl[begin])
        profit = cl[end] - cl[begin]
        l = lo[begin: end + 1]
        profit_low = min(l) - cl[begin]
        if profit_low <= - losscut:
            profit = -losscut
            position.exit_price = min(l)
            position.exit_index = np.argmin(l)
            position.exit_time = time[position.exit_index]
            position.losscutted = True
        else:
             position.exit_price = cl[end]
             position.exit_index = end
             position.exit_time = time[end]
        position.profit = profit
        return position        
        
    
    def short(self, time, cl, lo, hi, losscut, begin, end):
        position = Position(Signal.SHORT, begin, time[begin], cl[begin])
        profit = cl[begin] - cl[end]
        d = hi[begin: end + 1]
        profit_low = cl[begin] - max(d)
        if profit_low <= - losscut:
            profit = -losscut
            position.exit_price = max(d)
            position.exit_index = np.argmax(d)
            position.exit_time = time[position.exit_index]
            position.losscutted = True
        else:
             position.exit_price = cl[end]
             position.exit_index = end
             position.exit_time = time[end]
        position.profit = profit
        return position  

class Handler:
    
    def __init__(self, name, symbol, timeframe, repeat):
        self.name = name
        self.symbol = symbol
        self.timeframe = timeframe
        self.repeat = repeat
        self.result_dir(create=True)
        self.data = None
 
    def result_dir(self, create=False):     
        dir = os.path.join('./result/', self.name)
        if create:
            os.makedirs(dir, exist_ok=True)
        return dir        
   
    def load_data(self, from_year, from_month, to_year, to_month):
        loader = DataLoader()
        n, data = loader.load_data(self.symbol, self.timeframe, from_year, from_month, to_year, to_month)
        if n < 200:
            raise Exception('Data size is too small')           
        self.data = data        

        
    def run(self, trade_param, from_hour, from_minute, hours):
        sim = FastSimulator(trade_param)
        jst = self.data[Columns.JST]
        tend = jst[-1]
        t = datetime(jst[0].year, jst[0].month, jst[0].day, from_hour, from_minute)
        t0 = t.replace(tzinfo=JST)
        t1 = t0 + timedelta(hours=hours)
        trades = []
        while t0 < tend:
            n, d = Utils.sliceBetween(self.data, jst, t0, t1)
            if n > 20:
                trade = sim.run(d)
                plot(self.symbol, self.timeframe, d, trade)
                trades += trade
            t0 += timedelta(days=1)
            t1 = t0 + timedelta(hours=hours)
        s, acc, win_rate = Position.summary(trades)
        fig, ax = makeFig(1, 1, (10, 5))
        chart = CandleChart(fig, ax, date_format=CandleChart.DATE_FORMAT_DAY)
        chart.drawScatter(acc[0], acc[1])
        chart.drawLine(acc[0], acc[1])
        print(s, win_rate)
            
def plot(symbol, timeframe, data: dict, trades, chart_num=0):
    fig, axes = gridFig([2, 1], (10, 5))
    time = data[Columns.JST]
    title = symbol + '(' + timeframe + ')  ' + str(time[0]) + '...' + str(time[-1]) 
    chart1 = CandleChart(fig, axes[0], title=title, date_format=CandleChart.DATE_FORMAT_DATE_TIME)
    chart1.drawCandle(time, data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])

    chart1.drawLine(time, data[Indicators.ATR_TRAIL_UP], color='blue', linewidth=3.0)
    chart1.drawLine(time, data[Indicators.ATR_TRAIL_DOWN], color='red', linewidth=3.0)
    chart2 = CandleChart(fig, axes[1], title = title, write_time_range=True, date_format=CandleChart.DATE_FORMAT_DATE_TIME)
    chart2.drawLine(time, data[Indicators.ATR_TRAIL_TREND])
    #chart2.ylimit([0, 100])
    high = max(data[Columns.HIGH])
    low = min(data[Columns.LOW])
    for i, trade in enumerate(trades):
        if trade.signal == Signal.LONG:
            marker = '^'
            color = 'green'
        else:
            marker = 'v'
            color = 'red'
        chart1.drawMarker(trade.entry_time, trade.entry_price, marker, color, markersize=10.0)
        
        if trade.losscutted:
            marker = 'x'
        else:
            marker = 'o'
        if trade.signal == Signal.LONG:
            color = 'green'
            y = high
        else:
            color = 'red'
            y = low
        if trade.profit < 0:
            color = 'black'
        if trade.exit_price is not None:
            chart1.drawMarker(trade.exit_time, trade.exit_price, marker, 'gray', markersize=20.0)            
            chart1.drawMarker(trade.exit_time, y, '$' + str(i) + '$', color, markersize=15.0, alpha=0.9)            

def main():
    args = sys.argv
    if len(args) < 2:
        args = ['', 'DOW', 'M1']
    if len(args) < 4:
        number = 0
    else:
        number = int(args[3])
        
    symbol = args[1].upper()
    timeframe = args[2].upper()
    handler = Handler('ATRTrailFast', symbol, timeframe, 100)
    handler.load_data(2024, 2, 2024, 2)
    technical_param = {'atr_window': 10, 'atr_multiply': 3, 'peak_hold_term': 5 }
    indicators(handler.data, technical_param)
    trade_param = {'sl': 300, 'detect_count': 2}
    handler.run(trade_param, 22, 0, 4)
   
    
               
if __name__ == '__main__':

    main()
    #backtest('NIKKEI', 'M15')