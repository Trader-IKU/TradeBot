import pandas as pd
import numpy as np
from mt5_trade import Mt5Trade, Mt5TradeSim, TimeFrame, Columns, npdatetime2datetime
from datetime import datetime, timedelta

import pytz

JST = pytz.timezone('Asia/Tokyo')
UTC = pytz.timezone("UTC")
COLUMNS = [Columns.TIME, Columns.OPEN, Columns.HIGH, Columns.LOW, Columns.CLOSE, 'tick_volume']
TICK_COLUMNS = [Columns.TIME, Columns.ASK, Columns.BID]

def nans(length):
    return [np.nan for _ in range(length)]

def jst2utc(jst: datetime): 
    return jst.astimezone(UTC)

def np2pydatetime(times):
    out = []
    for time in times:
        dt = npdatetime2datetime(time)
        out.append(dt.astimezone(UTC))
    return out
    
def df2dic(df: pd.DataFrame, time_column: str, columns):
    dic = {}
    for column in columns:
        if column == time_column:
            dic[column] = np2pydatetime(df[time_column])
        else:
            dic[column] = list(df[column].values)
    return dic

class DataBuffer:
    def __init__(self, symbol: str, timeframe: str, df: pd.DataFrame):
        self.symbol = symbol
        self.timeframe = timeframe        
        self.data = df2dic(df, 'time', COLUMNS)

    def update(self, df: pd.DataFrame):
        dic = df2dic(df, 'time', COLUMNS)
        n = len(dic['time'])
        for timeframe, value in self.data.items():
            if timeframe in dic.keys():
                d = dic[timeframe]
                value += d
            else:
                value += nans(n)

class TickDataBuffer:
    def __init__(self, symbol: str, df: pd.DataFrame):
        self.symbol = symbol
        self.data = df2dic(df, Columns.TIME, TICK_COLUMNS)
        
    def update(self, df: pd.DataFrame):
        dic = df2dic(df, 'time', TICK_COLUMNS)
        
        for timeframe, value in self.data.items():
            d = dic[timeframe]
            value += d
        
class DataLoader:
    def __init__(self, symbol: str, timeframes:[str], server: Mt5Trade):
        self.symbol = symbol
        self.timeframes = timeframes
        self.server = server
        
    def debug_print(self):
        print('Current: ', self.current_time)
        m1 = self.buffers['M1'].data[Columns.TIME]
        tick = self.buffers['TICK'].data[Columns.TIME]
        print('   M1: ', m1[0], '-', m1[-2], m1[-1])
        print(' TICK: ', tick[0], '-', tick[-2], tick[-1])
        
    def run(self, jst_time_begin: datetime, passed: timedelta, step: timedelta):
        self.step = step
        self.current_time = jst_time_begin
        utc_time_begin = jst2utc(jst_time_begin)
        self.load_data(utc_time_begin - passed, utc_time_begin)        
        self.debug_print()
        
    def next(self, time: datetime=None):
        if time is None:
            next_time = self.current_time + self.step
        else:
            next_time = time 
        for timeframe, buffer in self.buffers.items():
            if timeframe == TimeFrame.TICK:
                df = self.server.get_ticks(self.current_time + timedelta(microseconds=1), next_time)
                buffer.update(df)
            else:
                df = self.server.get_rates(timeframe, self.current_time + timedelta(microseconds=1), next_time)
                buffer.update(df)
        self.current_time = next_time        
        self.debug_print()
                
    def load_data(self, utc_time0, utc_time1):
        dic = {}
        for timeframe in self.timeframes:
            if timeframe == TimeFrame.TICK:
                df = self.server.get_ticks(utc_time0, utc_time1)
                d = TickDataBuffer(self.symbol, df)
            else:
                df = self.server.get_rates(timeframe, utc_time0, utc_time1)
                d = DataBuffer(self.symbol, timeframe, df)
            dic[timeframe] = d
        self.buffers = dic
    