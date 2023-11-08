import pandas as pd
from mt5_trade import Mt5Trade, Mt5TradeSim, TimeFrame, npdatetime2datetime
from datetime import datetime, timedelta

from dateutil import tz

JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz("UTC")
COLUMNS = ['time', 'open', 'high', 'low', 'close', 'tick_volume']
TICK_COLUMNS = ['time', 'ask', 'bid']


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
        for timeframe, value in self.data.items():
            d = dic[timeframe]
            value += d

class TickDataBuffer:
    def __init__(self, symbol: str, df: pd.DataFrame):
        self.symbol = symbol
        self.dic = df2dic(df, 'time', TICK_COLUMNS)
        
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
        m1 = self.data['M1'].data['time']
        tick = self.data['TICK'].data['time']
        print('   M1: ', m1[0], '-', m1[-2], m1[-1])
        print(' TICK: ', tick[0], '-', tick[-2], tick[-1])
        
    def run(self, jst_time_begin: datetime, passed: timedelta, step: timedelta):
        self.step = step
        self.current_time = jst_time_begin
        utc_time_begin = jst2utc(jst_time_begin)
        self.load_data(utc_time_begin - passed, utc_time_begin)        
        self.debug_print()
        
    def next(self, time: datetime):
        if time is None:
            next_time = self.current_time + self.step
        else:
            next_time = time 
        for timeframe, data in self.dic.items():
            if timeframe == TimeFrame.TICK:
                df = self.server.get_ticks(self.current_time, next_time)
                data.update(df)
            else:
                df = self.server.get_rates(self.current_time, next_time)
                data.update(df)
        self.current_time = next_time        
        self.debug_print()
                
    def load_data(self, utc_time0, utc_time1):
        dic = {}
        for timeframe in self.timeframes:
            if timeframe == TimeFrame.TICK:
                df = self.server.get_ticks(utc_time0, utc_time1)
                d = TickDataBuffer(self.symbol, df)
            else:
                df = self.server.get_rates(utc_time0, utc_time1)
                d = DataBuffer(self.symbol, timeframe, df)
            dic[timeframe] = d
        self.data = dic
    