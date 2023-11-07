import pandas as pd
from mt5_trade import Mt5Trade, Mt5TradeSim, TimeFrame, npdatetime2datetime
from DateTime import DateTime, timedelta

from dateutil import tz
JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz("UTC")

def jst2utc(jst: DateTime): 
    return jst.astimezone(UTC)

def np2pydatetime(times):
    return [npdatetime2datetime(t) for t in times]
    
def df2dic(df: pd.DataFrame, time_column: str):
    dic = {}
    for column in df.columns:
        if column == time_column:
            dic[column] = np2pydatetime(df[time_column])
        else:
            dic[column] = list(df[column].values)
    return dic

class DataBuffer:
    def __init__(self, symbol: str, timeframe: str, df: pd.DataFrame):
        self.symbol = symbol
        self.timeframe = timeframe        
        self.dic = df2dic(df, 'time')

    def update(self, df: pd.DataFrame):
        dic = df2dic(df, 'time')
        for timeframe, data in self.dic.items():
            d = dic[timeframe]
            data += d

class TickDataBuffer:
    def __init__(self, symbol: str, df: pd.DataFrame):
        self.symbol = symbol
        self.dic = df2dic(df, 'time')
        
    def update(self, df: pd.DataFrame):
        dic = df2dic(df, 'time')
        for timeframe, data in self.dic.items():
            d = dic[timeframe]
            data += d
        
class DataLoader:
    def __init__(self, symbol: str, timeframes:[str], server: Mt5Trade):
        self.symbol = symbol
        self.timeframes = timeframes
        self.server = server
        
    def run(self, jst_time_begin: DateTime, passed: timedelta, step: timedelta):
        self.step = step
        self.current_time = jst_time_begin
        utc_time_begin = jst2utc(jst_time_begin)
        self.load_data(utc_time_begin - passed, utc_time_begin)        
        
    def next(self, time: DateTime):
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
        
        
    def load_data(self, utc_time0, utc_time1):
        dic = {}
        for timeframe in self.timeframes():
            if timeframe == TimeFrame.TICK:
                df = self.server.get_ticks(utc_time0, utc_time1)
                data = TickDataBuffer(self.symbol, df)
            else:
                df = self.server.get_rates(utc_time0, utc_time1)
                data = DataBuffer(self.symbol, timeframe, df)
            dic[timeframe] = data
        self.dic = dic
    