import os
import sys
sys.path.append('../Libraries/trade')

import numpy as np
import pandas as pd
import pytz
from datetime import datetime, timedelta
from mt5_trade import Columns
from technical import Indicators, add_indicators, supertrend_trade
from candle_chart import CandleChart, makeFig
from data_loader import df2dic
from time_utils import TimeUtils

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

def load_data(symbol, timeframe):
    path = '../MarketData/Axiory/'
    dir_path = os.path.join(path, symbol, timeframe)
    dfs = []
    for year in [2023]:
        for month in range(1, 13):
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

def plot(data: dict):
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
        n, d = TimeUtils.slice(data, time, t, t1)
        if n > 20:   
            fig, ax = makeFig(1, 1, (20, 10))
            chart = CandleChart(fig, ax)
            chart.drawCandle(d[Columns.TIME], d[Columns.OPEN], d[Columns.HIGH], d[Columns.LOW], d[Columns.CLOSE])
            chart.drawLine(d[Columns.TIME], d['MA9'], color='blue')
            chart.drawLine(d[Columns.TIME], d[Indicators.SUPERTREND_U], color='red', linewidth=2.0)
            chart.drawLine(d[Columns.TIME], d[Indicators.SUPERTREND_L], color='green', linewidth=2.0)
        t += timedelta(days=7)
        
def simulation(symbol, timeframe):
    data = load_data(symbol, timeframe)
    out = []
    for ma_window in [20, 40, 60]:
        for atr_window in [5, 7, 15, 25]:
            for atr_multiply in [0.5, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0]: 
                for k_losscut in [0.2, 0.5, 1.0, 1.5, 2.0]:   
                    for tolerance in [1e-8, 1e-6, 1e-5, 1e-4]:
                        params= {'MA':{'window':ma_window}, 'ATR': {'window':atr_window, 'multiply': atr_multiply}}
                        print('** ' + symbol + ' ' + timeframe + ' **')
                        print('k-losscut:', k_losscut, 'tolerance: ', tolerance, params)
                        add_indicators(data, params)
                        trades = supertrend_trade(data, params, k_losscut, tolerance)
                        result = []
                        for trade in trades:
                            d, columns = trade.array()
                            result.append(d)
                        df = pd.DataFrame(data=result, columns=columns)
                        num = len(df)
                        profit = df['Profit'].sum()
                        print('  -> Profit: ' +  str(profit) + ' num: ' + str(num))
                        out.append([symbol, timeframe, params['MA']['window'], params['ATR']['window'], params['ATR']['multiply'], k_losscut, tolerance, profit, num])
    
    result = pd.DataFrame(data=out, columns=['symbol', 'timeframe', 'ma_window', 'atr_window', 'atr_multiply', 'k_losscut', 'tolerance', 'profit', 'num'])
    result.to_excel('./summary' + '_' + symbol + '_' + timeframe + '.xlsx', index=False)
    #df.to_csv('./trade_result.csv', index=False)
    #print('data size: ', len(data['time']))
    #plot(data)

if __name__ == '__main__':
    for timeframe in ['M30']:
        simulation('NIKKEI', timeframe)