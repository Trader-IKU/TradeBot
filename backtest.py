import os
import sys
sys.path.append('../Libraries/trade')

import numpy as np
import pandas as pd
import pytz
from datetime import datetime, timedelta
from common import Columns, Signal, Indicators
from technical import add_indicators, supertrend_trade
from candle_chart import CandleChart, makeFig, gridFig
from data_buffer import df2dic
from time_utils import TimeUtils
from utils import Utils

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('./trade.log')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def utc_str_2_jst(utc_str_list, format='%Y-%m-%d %H:%M:%S'):
    out = []
    for utc_str in utc_str_list:
        utc = datetime.strptime(utc_str, format) 
        utc = pytz.timezone('UTC').localize(utc)
        jst = utc.astimezone(pytz.timezone('Asia/Tokyo'))        
        out.append(jst)
    return out

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
    jst = utc_str_2_jst(dic[Columns.TIME])
    dic[Columns.TIME] = jst
    print('Data size:', len(jst), jst[0], '-', jst[-1])
    return dic

def trade_summary(trades):
    n = len(trades)
    s = 0
    minv = maxv = None
    for trade in trades:
        if trade.profit is None:
            continue
        s += trade.profit
        if minv is None:
            minv = maxv = s
        else:
            if s < minv:
                minv = s
            if s > maxv:
                maxv = s
    return n, s, minv, maxv

def pickup_trade(trades, tbegin, tend):
    out = []
    for trade in trades:
        if trade.open_time >= tbegin and trade.open_time <= tend:
            out.append(trade)
    return out

def plot(data: dict, params, trades):
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
        if n > 20:   

            fig, axes = gridFig([5, 1], (20, 10))
            chart = CandleChart(fig, axes[0])
            chart.drawCandle(d[Columns.TIME], d[Columns.OPEN], d[Columns.HIGH], d[Columns.LOW], d[Columns.CLOSE])
            name = 'MA' + str(params['MA']['window'])
            chart.drawLine(d[Columns.TIME], d[name], color='blue')
            chart.drawLine(d[Columns.TIME], d[Indicators.SUPERTREND_U], color='red', linewidth=2.0)
            chart.drawLine(d[Columns.TIME], d[Indicators.SUPERTREND_L], color='green', linewidth=2.0)
            
            chart2 = CandleChart(fig, axes[1])
            chart2.drawLine(d[Columns.TIME], d[Indicators.SUPERTREND])
            
            trs = pickup_trade(trades, t, t1)
            for trade in trs:
                trade.desc()
                if trade.signal == Signal.LONG:
                    marker = '^'
                    color = 'green'
                else:
                    marker = 'v'
                    color = 'red'
                chart.drawMarker(trade.open_time, trade.open_price, marker, color)
                
                if trade.losscutted:
                    marker = 'x'
                else:
                    marker = 'o'
                chart.drawMarker(trade.close_time, trade.close_price, marker, color)
            
        t += timedelta(days=7)
        
def simulation_monthly(symbol, timeframe, year, month, sl, tp, inverse=False):
    data0 = load_data(symbol, timeframe, [year], [month])
    out = []
    for atr_window in [5, 7, 15, 25]:
        for atr_multiply in [0.5, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0]: 
            params= {'ATR': {'window':atr_window, 'multiply': atr_multiply}}
            data = data0.copy()
            add_indicators(data, params)
            print('**', year, month, symbol + ' ' + timeframe + ' **')
            for losscut in sl:
                for take in tp:
                    for entry_horizon in [0, 1, 2]:
                        for exit_horizon in [0, 1, 2]:       
                            tolerance = 1e-8
                            print('losscut:', losscut, 'takeprofit:', take, 'entry_horizon', entry_horizon, 'exit_horizon', exit_horizon, inverse, params)
                            trades = supertrend_trade(data, params, losscut, take, entry_horizon, exit_horizon, tolerance, inverse=inverse)
                            num, profit, drawdown, vmax = trade_summary(trades)
                            print('  -> Profit: ', profit, 'Drawdown:', drawdown, ' num: ' + str(num))
                            out.append([symbol, timeframe, params['ATR']['window'], params['ATR']['multiply'], losscut, take, entry_horizon, exit_horizon, tolerance, profit, drawdown, num])
    result = pd.DataFrame(data=out, columns=['symbol', 'timeframe', 'atr_window', 'atr_multiply', 'sl', 'tp', 'entry_horizon', 'exit_horizon', 'tolerance', 'profit', 'drawdown', 'num'])
    return result
    #result.to_excel('./result/summary' + '_'  + symbol + '_' + timeframe + '_' + str(year) + '-' + str(month) +'.xlsx', index=False)
    #df.to_csv('./trade_result.csv', index=False)
    #print('data size: ', len(data['time']))
    #plot(data)

def simulation(symbol, timeframe, df_param, inverse=False):
    data0 = load_data(symbol, timeframe, [2020, 2021, 2022, 2023], range(1, 13))
    out = []
    for row in range(len(df_param)):
        print(row, '/', len(df_param))
        data = data0.copy()
        d = df_param.iloc[row, :]
        atr_window = d['atr_window']
        atr_multiply = d['atr_multiply']
        entry = d['entry_horizon']
        ext = d['exit_horizon']
        losscut = d['sl']
        takeprofit = d['tp']  
        tolerance = 1e-8
        params= {'ATR': {'window':atr_window, 'multiply': atr_multiply}}
        print('** ' + symbol + ' ' + timeframe + ' **')
        print('losscut:', losscut, 'takeprofit:', takeprofit, params)
        add_indicators(data, params)
        trades = supertrend_trade(data, params, losscut, takeprofit, entry, ext, tolerance, inverse=inverse)
        num, profit, drawdown, maxv = trade_summary(trades)
        print('  -> Profit: ', profit, 100 * profit / data[Columns.CLOSE][0], ' num: ' + str(num))
        out.append([symbol, timeframe, params['ATR']['window'], params['ATR']['multiply'], losscut, takeprofit, entry, ext, tolerance, profit, 100 * profit / data[Columns.CLOSE][0], drawdown, num])
    result = pd.DataFrame(data=out, columns=['symbol', 'timeframe', 'atr_window', 'atr_multiply', 'sl', 'tp', 'entry_horizon', 'exit_horizon', 'tolerance', 'profit', 'profit_percent', 'drawdown', 'num'])
    result = result.sort_values('profit', ascending=False)
    result.to_excel('./result/best' + '_' + symbol + '_' + timeframe + '.xlsx', index=False)
    #df.to_csv('./trade_result.csv', index=False)
    #print('data size: ', len(data['time']))
    #plot(data)

def backtest(symbol, timeframe, sl, tp, best_num=50, inverse=False):
    year = 2023
    dfs = []
   
    for year in [2020, 2021, 2022, 2023]:
        for month in range(1, 13):
            df = simulation_monthly(symbol, timeframe, year, month, sl, tp, inverse=inverse)
            df = df.sort_values('profit', ascending=False)
            if len(df) > best_num:
                df = df.iloc[:best_num, :]
            dfs.append(df)
    df_param = pd.concat(dfs, ignore_index=True)
    df_param = df_param.drop(['profit', 'drawdown', 'num'], axis=1)
    df_param = df_param.duplicated()
    df_param = df_param.reset_index()
    simulation(symbol, timeframe, df_param, inverse=inverse)
    
def test():
    symbol = 'NIKKEI'
    timeframe = 'M30'
    data = load_data(symbol, timeframe)
    ma_window = 60
    atr_window = 5
    atr_multiply = 2.0 
    stoploss = 200
    tolerance = 1e-6
    params= {'MA':{'window':ma_window}, 'ATR': {'window':atr_window, 'multiply': atr_multiply}}
    print('** ' + symbol + ' ' + timeframe + ' **')
    print('stoploss:', stoploss, 'tolerance: ', tolerance, params)
    add_indicators(data, params)
    trades = supertrend_trade(data, params, stoploss, tolerance)   
    trade_summary(trades)
    plot(data, params, trades) 


def backtest1():
    # dow, nikkei 30000
    sl = [100, 150, 200, 250, 300]
    tp = [0] + sl
    backtest('NIKKEI', 'M30', sl, tp)
    backtest('NIKKEI', 'M15', sl, tp)
    #backtest('NIKKEI', 'M5', sl, tp)
    backtest('DOW', 'M30', sl, tp)
    backtest('DOW', 'M15', sl, tp)
    #backtest('DOW', 'M5', sl, tp)    
       
def backtest2():
    # nasdaq 8000
    sl = [20, 50, 70, 100]
    tp = [0] + sl
    backtest('NSDQ', 'M30', sl, tp)
    backtest('NSDQ', 'M15', sl, tp)
    #backtest('NSDQ', 'M5', sl, tp)
    
    # nasdaq 20000
    sl = [50, 70, 100, 200]
    tp = [0] + sl
    backtest('HK50', 'M30', sl, tp)
    backtest('HK50', 'M15', sl, tp)
    #backtest('NSDQ', 'M5', sl, tp)  
    
def backtest3():
   
    # gold 1500
    sl = [0.5, 1, 2, 5, 7, 10, 20]
    tp = [0] + sl
    backtest('XAUUSD', 'M30', sl, tp)
    backtest('XAUUSD', 'M15', sl, tp)
    #backtest('XAUUSD', 'M5', sl, tp)     

    # oil 70
    sl = [0.05, 0.1, 0.2, 0.5, 0.7, 0.1, 0.2]
    tp = [0] + sl
    backtest('CL', 'M30', sl, tp)
    backtest('CL', 'M15', sl, tp)
    #backtest('CL', 'M5', sl, tp)
    
     # ngas 2.0
    sl = [0.001, 0.002, 0.005, 0.007, 0.01]
    tp = [0] + sl
    backtest('NGAS', 'M30', sl, tp)
    backtest('NGAS', 'M15', sl, tp)
    #backtest('NGAS', 'M5', sl, tp)
    
def backtest4():
    # gbpjpy, usdjpy 150
    sl = [0.05, 0.1, 0.2, 0.5, 0.7, 0.1]
    tp = [0] + sl
    backtest('USDJPY', 'M30', sl, tp)
    backtest('USDJPY', 'M15', sl, tp)
    #backtest('USDJPY', 'M5', sl, tp)
    backtest('GBPJPY', 'M30', sl, tp)
    backtest('GBPJPY', 'M15', sl, tp)
    #backtest('GBPJPY', 'M5', sl, tp)
    
def backtest5():
    # dow, nikkei 30000
    sl = [50, 100, 150, 200]
    tp = [0] + sl
    backtest('NIKKEI', 'M1', sl, tp, inverse=True)
    
    
def backtest6():
    # dow, nikkei 30000
    sl = [50, 100, 150, 200]
    tp = [0] + sl
    
    backtest('DOW', 'M1', sl, tp, inverse=True)
       
    # nasdaq 8000
    sl = [20, 50, 70]
    tp = [0] + sl
    backtest('NSDQ', 'M1', sl, tp, inverse=True)
    
def backtest7():
    # gold 1500
    sl = [0.5, 1, 2, 5, 7, 10]
    tp = [0] + sl
    backtest('XAUUSD', 'M1', sl, tp, inverse=True)
    # oil 70
    sl = [0.05, 0.1, 0.2, 0.5]
    tp = [0] + sl
    backtest('CL', 'M1', sl, tp, inverse=True)
    
     # ngas 2.0
    sl = [0.001, 0.002, 0.005]
    tp = [0] + sl
    backtest('NGAS', 'M1', sl, tp, inverse=True)
    
def backtest8():
    # gbpjpy, usdjpy 150
    sl = [0.05, 0.1, 0.2, 0.5]
    tp = [0] + sl
    backtest('USDJPY', 'M1', sl, tp, inverse=True)
    
def backtest9():
    # gbpjpy, usdjpy 150
    sl = [0.05, 0.1, 0.2, 0.5]
    tp = [0] + sl
    backtest('GBPJPY', 'M1', sl, tp, inverse=True)
    
def backtest10():
    backtest('EURUSD', 'M1', sl, tp, inverse=True)
    backtest('AUDJPY', 'M1', sl, tp, inverse=True)
        
def main():
    backtest3()
 
if __name__ == '__main__':
    main()