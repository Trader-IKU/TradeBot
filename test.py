import os
import sys
sys.path.append('../Libraries/trade')

from backtest_ga import load_data
from mt5_trade import Mt5TradeSim, Columns, JST, UTC
from datetime import datetime, timedelta
from candle_chart import CandleChart, makeFig
import matplotlib.pyplot as plt
from technical import *
from backtest_ga import server_time_str_2_datetime
from time_utils import TimeUtils
from utils import Utils
from dateutil import tz
JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc')  



def plot(data: dict):
    fig, ax = makeFig(1, 1, (10, 7))
    chart = CandleChart(fig, ax)
    chart.drawCandle(data[Columns.TIME], data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])
    chart.drawLine(data[Columns.TIME], data['MA5'], color='blue')
    chart.drawLine(data[Columns.TIME], data[Indicators.ATR_U], color='green')
    chart.drawLine(data[Columns.TIME], data[Indicators.ATR_L], color='red')
    ax2 = ax.twinx()
    chart2 = CandleChart(fig, ax2)
    #chart2.drawLine(data[Columns.TIME], data['VOLATILITY'], color='orange', linewidth=2.0)
    ax3 = ax.twinx()
    chart3 = CandleChart(fig, ax3)
    chart3.drawLine(data[Columns.TIME], data['ATR'], color='blue', linewidth=2.0)
    plt.show()
    pass

def pickup_trade(trades, tbegin, tend):
    out = []
    for trade in trades:
        if trade.open_time >= tbegin and trade.open_time <= tend:
            out.append(trade)
    return out

def plot_daily(data):
    time = data[Columns.TIME]
    t = time[0]
    t = datetime(t.year, t.month, t.day, tzinfo=JST)
    tend = time[-1]
    tend = datetime(tend.year, tend.month, tend.day, tzinfo=JST) + timedelta(days=1)
    
    while t < tend:
        t1 = t + timedelta(days=1)
        try:
            n, d = Utils.sliceBetween(data, time, t, t1)
            if n < 40:
                continue
        except:
            t += timedelta(days=1)
            continue
        plot(d)
        plt.show()
        t += timedelta(days=1)
        
        
def plot_week(data: dict):
    def next_monday(t: datetime):
        t1 = t
        while True:
            if t1.weekday() == 0:
                return t1
            t1 += timedelta(days=1)           
                
    time = data[Columns.TIME]
    t = next_monday(time[0])
    t = datetime(t.year, t.month, t.day, tzinfo=JST)
    tend = time[-1]
    tend = datetime(tend.year, tend.month, tend.day, tzinfo=JST) + timedelta(days=7)
    
    while t < tend:
        t1 = t + timedelta(days=7)
        try:
            n, d = Utils.sliceBetween(data, time, t, t1)
        except:
            t += timedelta(days=7)
            continue
        plot(d)
        t += timedelta(days=7)        
        
        
        
        
def test():
    symbol = 'USDJPY'
    timeframe = 'M15'
    params = {'MA':{'window': 60}, 'VOLATILITY':{'window': 50}, 'ATR': {'window': 20, 'multiply':2.0}}
    
    data = load_data(symbol, timeframe, [2023], [11])
    MA(data, Columns.CLOSE, 5)
    ATR(data, 15, 2.0)
    ADX(data, 15, 15)
    supertrend(data)
    
    plot_week(data)
    pass
    
if __name__ == '__main__':
    test()