# -*- coding: utf-8 -*-
"""
Created on Sun Nov  5 21:44:13 2023

@author: docs9
"""

import os
import sys
sys.path.append('../Libraries/trade')

import pandas as pd
from datetime import datetime, timedelta
from dateutil import tz
from dateutil.relativedelta import relativedelta
from mt5_trade import Mt5Trade
from common import TimeFrame
from datetime import datetime, timedelta, timezone
from time_utils import TimeUtils
JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc')  

def server_time(begin_month, begin_sunday, end_month, end_sunday, delta_hour_from_gmt_in_summer):
    now = datetime.now(JST)
    dt, tz = TimeUtils.delta_hour_from_gmt(now, begin_month, begin_sunday, end_month, end_sunday, delta_hour_from_gmt_in_summer)
    #delta_hour_from_gmt  = dt
    #server_timezone = tz
    #print('SeverTime GMT+', dt, tz)
    return dt, tz  
  
def adjust_summer_time(time: datetime):
    dt, tz = server_time(3, 2, 11, 1, 3.0)
    return time - dt

def adjust(dic):
    utc = dic['time']
    time = []
    for ts in utc:
        t = pd.to_datetime(ts)
        t = t.replace(tzinfo=UTC)
        time.append(adjust_summer_time(t))
    dic['time'] = time
    
def download(symbols, save_holder):
    trading = Mt5Trade(symbols[0])
    trading.connect()
    for symbol in symbols:
        trading.symbol = symbol
        for tf in [TimeFrame.W1, TimeFrame.M1, TimeFrame.M5, TimeFrame.M15, TimeFrame.M30, TimeFrame.H1, TimeFrame.H4, TimeFrame.D1]:
            for year in range(2024, 2025):
                for month in range(4, 5):
                    t0 = datetime(year, month, 1, tzinfo=timezone.utc)
                    t1 = t0 + relativedelta(months=1) - timedelta(seconds=1)
                    if tf == 'TICK':
                        rates = trading.get_ticks(t0, t1)
                    else:
                        rates = trading.get_rates_utc(tf, t0, t1)
                    adjust(rates)
                    if len(rates) > 1:
                        path = os.path.join(save_holder, symbol, tf)
                        os.makedirs(path, exist_ok=True)
                        path = os.path.join(path, symbol + '_' + tf + '_' + str(year) + '_' + str(month).zfill(2) + '.csv')
                        rates.to_csv(path, index=False)
                    print(symbol, tf, year, '-', month, 'size: ', len(rates))
    
    pass

def dl1():
    symbols = ['NIKKEI', 'DOW', 'NSDQ', 'SP', 'HK50', 'DAX', 'FTSE', 'XAUUSD']
    symbols += ['CL', 'USDJPY', 'GBPJPY']
    symbols += ['HK50', 'NGAS', 'EURJPY', 'AUDJPY', 'EURUSD']
    download(symbols, '../MarketData/Axiory/')
    
def dl2():
    symbols = ['SP', 'HK50', 'DAX', 'FTSE',  'XAGUSD', 'EURJPY', 'AUDJPY']
    symbols = ['NIKKEI', 'USDJPY']
    download(symbols, '../MarketData/Axiory/')
    
    
if __name__ == '__main__':
    dl1()

