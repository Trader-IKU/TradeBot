import os
import sys
sys.path.append('../Libraries/trade')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pytz
from datetime import datetime, timedelta, timezone
from dateutil import tz
from common import Columns, Signal, Indicators
from technical import add_indicators, supertrend_trade, trade_summary, SL_TP_TYPE_NONE, SL_TP_TYPE_FIX, SL_TP_TYPE_AUTO
from candle_chart import CandleChart, makeFig, gridFig
from data_buffer import df2dic
from time_utils import TimeUtils
from utils import Utils


JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc')  


import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('./trade.log')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

GENETIC_COLUMNS = ['atr_window', 'atr_multiply', 'sl_type', 'sl', 'tp_type', 'tp', 'entry_delay', 'exit_delay', 'timeup_minutes', 'inverse']

def server_time_str_2_datetime(server_time_str_list, server_timezone, format='%Y-%m-%d %H:%M:%S'):
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

def load_data(symbol, timeframe, years, months):
    path = '../MarketData/Axiory/'
    dir_path = os.path.join(path, symbol, timeframe)
    dfs = []
    for year in years:
        for month in months:
            name = symbol + '_' + timeframe + '_' + str(year) + '_' + str(month).zfill(2) + '.csv'
            try:
                d = pd.read_csv(os.path.join(dir_path, name))
                dfs.append(d[[Columns.TIME, Columns.OPEN, Columns.HIGH, Columns.LOW, Columns.CLOSE]])
            except:
                print('Error in', name)
                continue
    df = pd.concat(dfs, ignore_index=True)
    dic = {}
    for column in df.columns:
        dic[column] = list(df[column].values)
    tzone = timezone(timedelta(hours=2))
    utc, jst = server_time_str_2_datetime(dic[Columns.TIME], tzone)
    dic[Columns.TIME] = utc
    dic[Columns.JST] = jst
    print(symbol, timeframe, 'Data size:', len(jst), jst[0], '-', jst[-1])
    return dic

def pickup_trade(trades, tbegin, tend):
    out = []
    for trade in trades:
        if trade.open_time >= tbegin and trade.open_time <= tend:
            out.append(trade)
    return out

def plot(data: dict, trades):

    fig, axes = gridFig([5, 1], (20, 10))
    chart = CandleChart(fig, axes[0])
    chart.drawCandle(data[Columns.TIME], data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])
    #name = 'MA' + str(params['MA']['window'])
    #chart.drawLine(data[Columns.TIME], data[name], color='blue')
    chart.drawLine(data[Columns.TIME], data[Indicators.SUPERTREND_U], color='red', linewidth=2.0)
    chart.drawLine(data[Columns.TIME], data[Indicators.SUPERTREND_L], color='green', linewidth=2.0)
    
    ax = axes[0].twinx()
    chart2 = CandleChart(fig, ax)
    chart2.drawLine(data[Columns.TIME], data[Indicators.SUPERTREND])
    
    chart3 = CandleChart(fig, axes[1])
    chart3.drawLine(data[Columns.TIME], data[Indicators.SUPERTREND])
    
    
    for i, trade in enumerate(trades):
        trade.desc()
        if trade.signal == Signal.LONG:
            marker = '^'
            color = 'green'
        else:
            marker = 'v'
            color = 'red'
        chart.drawMarker(trade.open_time, trade.open_price, marker, color, overlay=i)
        
        if trade.losscutted:
            marker = 'x'
        elif trade.profittaken:
            marker = '*'
        elif trade.time_upped:
            marker = 's'
        else:
            marker = 'o'
        if trade.profit is not None:
            if trade.profit < 0:
                color = 'gray'
        chart.drawMarker(trade.close_time, trade.close_price, marker, color, overlay=i)            
    plt.show()
        
def plot_week(data: dict, trades):
    def next_monday(t: datetime):
        t1 = t
        while True:
            if t1.weekday() == 0:
                return t1
            t1 += timedelta(days=1)           
                
    time = data[Columns.TIME]
    t = next_monday(time[0])
    t = datetime(t.year, t.month, t.day, tzinfo=pytz.timezone('Asia/Tokyo'))
    tend = time[-1]
    tend = datetime(tend.year, tend.month, tend.day, tzinfo=pytz.timezone('Asia/Tokyo')) + timedelta(days=7)
    
    while t < tend:
        t1 = t + timedelta(days=7)
        try:
            n, d = Utils.sliceBetween(data, time, t, t1)
        except:
            t += timedelta(days=7)
            continue
        trds = pickup_trade(trades, t, t1)
        plot(d, trds)
        t += timedelta(days=7)
        
        
def plot_daily(data, trades):
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
        trds = pickup_trade(trades, t, t1)
        plot(d, trds)
        t += timedelta(days=1)
    
def backtest(symbol, timeframe):
    data = load_data(symbol, timeframe, [2023], range(4, 7))
    atr_window = 60
    param = {'ATR': {'window': atr_window, 'multiply': 4.0}}
    add_indicators(data, param)
    
    sl_type = SL_TP_TYPE_AUTO
    sl = 1.0
    tp_type = SL_TP_TYPE_NONE
    risk_reward = 1.0
    entry_hold = 1
    exit_hold = 1
    timeup = 50
    inverse = 1
    
    trades = supertrend_trade(data, atr_window, sl_type, sl, tp_type, risk_reward, entry_hold, exit_hold, timeup, inverse)
    #plot(data, trades)
    num, profit, drawdown, maxv, win_rate = trade_summary(trades)
    if num > 0 : #and profit_acc > 0:        
        print(num, profit)

def main():
    symbol = 'USDJPY'
    timeframe = 'M30'
    backtest(symbol, timeframe)
 
if __name__ == '__main__':
    main()