import os
import sys
sys.path.append('../Libraries/trade')

import numpy as np
import pandas as pd
import pytz
from datetime import datetime, timedelta
from mt5_trade import Columns
from technical import Signal, Indicators, add_indicators, supertrend_trade
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
        
def simulation_monthly(symbol, timeframe, year, month, losscuts):
    data0 = load_data(symbol, timeframe, [year], [month])
    out = []
    for ma_window in [60]:
        for atr_window in [5, 7, 15, 25]:
            for atr_multiply in [0.5, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0]: 
                for losscut in losscuts:
                    for entry in [Columns.OPEN, Columns.CLOSE]:
                        for ext in [Columns.OPEN, Columns.CLOSE]:
                            data = data0.copy()
                            tolerance = 1e-8
                            params= {'MA':{'window':ma_window}, 'ATR': {'window':atr_window, 'multiply': atr_multiply}}
                            print('** ' + symbol + ' ' + timeframe + ' **')
                            print('losscut:', losscut, 'tolerance: ', tolerance, params)
                            add_indicators(data, params)
                            trades = supertrend_trade(data, params, losscut, entry, ext, tolerance)
                            num, profit, drawdown, vmax = trade_summary(trades)
                            print('  -> Profit: ' +  str(profit) + ' num: ' + str(num))
                            out.append([symbol, timeframe, params['MA']['window'], params['ATR']['window'], params['ATR']['multiply'], losscut, entry, ext, tolerance, profit, drawdown, num])
    
    result = pd.DataFrame(data=out, columns=['symbol', 'timeframe', 'ma_window', 'atr_window', 'atr_multiply', 'losscut', 'entry', 'exit', 'tolerance', 'profit', 'drawdown', 'num'])
    return result
    #result.to_excel('./result/summary' + '_'  + symbol + '_' + timeframe + '_' + str(year) + '-' + str(month) +'.xlsx', index=False)
    #df.to_csv('./trade_result.csv', index=False)
    #print('data size: ', len(data['time']))
    #plot(data)

def simulation(symbol, timeframe, df_param):
    data0 = load_data(symbol, timeframe, [2023], range(1, 12))
    out = []
    for row in range(len(df_param)):
        print(row, '/', len(df_param))
        data = data0.copy()
        d = df_param.iloc[row, :]
        ma_window = d['ma_window']
        atr_window = d['atr_window']
        atr_multiply = d['atr_multiply']
        entry = d['entry']
        ext = d['exit']
        losscut = d['losscut']  
        tolerance = 1e-8
        params= {'MA':{'window':ma_window}, 'ATR': {'window':atr_window, 'multiply': atr_multiply}}
        print('** ' + symbol + ' ' + timeframe + ' **')
        print('losscut:', losscut, 'tolerance: ', tolerance, params)
        add_indicators(data, params)
        trades = supertrend_trade(data, params, losscut, entry, ext, tolerance)
        num, profit, drawdown, maxv = trade_summary(trades)
        print('  -> Profit: ', profit, 100 * profit / data[Columns.CLOSE][0], ' num: ' + str(num))
        out.append([symbol, timeframe, params['MA']['window'], params['ATR']['window'], params['ATR']['multiply'], losscut, entry, ext, tolerance, profit, 100 * profit / data[Columns.CLOSE][0], drawdown, num])
    result = pd.DataFrame(data=out, columns=['symbol', 'timeframe', 'ma_window', 'atr_window', 'atr_multiply', 'losscut', 'entry', 'exit', 'tolerance', 'profit', 'profit_percent', 'drawdown', 'num'])
    result.to_excel('./result/best' + '_' + symbol + '_' + timeframe + '.xlsx', index=False)
    #df.to_csv('./trade_result.csv', index=False)
    #print('data size: ', len(data['time']))
    #plot(data)

def backtest(symbol, timeframe, losscuts):
    year = 2023
    dfs = []
   
    for month in range(1, 12):
        df = simulation_monthly(symbol, timeframe, year, month, losscuts)
        df = df.sort_values('profit', ascending=False)
        if len(df) > 100:
            df = df.iloc[:100, :]
        dfs.append(df)
    df_param = pd.concat(dfs, ignore_index=True)
    simulation(symbol, timeframe, df_param)
    
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

    
def main():
    # dow, nikkei 30000
    losscuts = [50, 100, 150, 200, 250]
    #backtest('NIKKEI', 'M30', losscuts)
    backtest('NIKKEI', 'M15', losscuts)
    #backtest('NIKKEI', 'M5', losscuts)
    #backtest('DOW', 'M30', losscuts)
    backtest('DOW', 'M15', losscuts)
    #backtest('DOW', 'M5', losscuts)
    
    # nasdaq 8000
    losscuts = [5, 10, 20, 50, 70, 100]
    #backtest('NSDQ', 'M30', losscuts)
    backtest('NSDQ', 'M15', losscuts)
    #backtest('NSDQ', 'M5', losscuts)
    
    # ngas 2.0
    losscuts = [0.001, 0.002, 0.005, 0.007, 0.01, 0.02]
    #backtest('NGAS', 'M30', losscuts)
    backtest('NGAS', 'M15', losscuts)
    #backtest('NGAS', 'M5', losscuts)
    
    # gold 1500
    losscuts = [0.5, 1, 2, 5, 7, 10, 15, 20]
    #backtest('XAUUSD', 'M30', losscuts)
    backtest('XAUUSD', 'M15', losscuts)
    #backtest('XAUUSD', 'M5', losscuts)
    
    
    # gbpjpy, usdjpy 150
    losscuts = [0.05, 0.1, 0.2, 0.5, 0.7, 0.10, 0.2]
    #backtest('USDJPY', 'M30', losscuts)
    backtest('USDJPY', 'M15', losscuts)
    #backtest('USDJPY', 'M5', losscuts)
    #backtest('GBPJPY', 'M30', losscuts)
    backtest('GBPJPY', 'M15', losscuts)
    #backtest('GBPJPY', 'M5', losscuts)
    
    # oil 70
    losscuts = [0.025, 0.05, 0.1, 0.2, 0.5, 0.7, 0.1, 0.2, 0.5]
    #backtest('CL', 'M30', losscuts)
    backtest('CL', 'M15', losscuts)
    #backtest('CL', 'M5', losscuts)
    
if __name__ == '__main__':
    main()