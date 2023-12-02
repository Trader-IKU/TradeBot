import pandas as pd
import numpy as np
from mt5_trade import Mt5Trade, TimeFrame, Columns, npdatetime2datetime
from datetime import datetime, timedelta
from technical import Signal, Indicators, add_indicators, supertrend_trade

import pytz

JST = pytz.timezone('Asia/Tokyo')
UTC = pytz.timezone("UTC")
COLUMNS = [Columns.TIME, Columns.OPEN, Columns.HIGH, Columns.LOW, Columns.CLOSE, 'tick_volume']
TICK_COLUMNS = [Columns.TIME, Columns.ASK, Columns.BID]

def nans(length):
    return [np.nan for _ in range(length)]

def jst2utc(jst: datetime): 
    return jst.astimezone(UTC)

def utcstr2datetime(utc_str: str, format='%Y-%m-%d %H:%M:%S'):
    utc = datetime.strptime(utc_str, format)
    utc = pytz.timezone('UTC').localize(utc)
    return utc

def utc2jst(utc: datetime):
    jst = utc.astimezone(pytz.timezone('Asia/Tokyo'))       
    return jst

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
            utc = np2pydatetime(df[time_column])
            dic[column] = utc
            jst = [utc2jst(t) for t in utc]
            dic[Columns.JST] = jst
            
        else:
            dic[column] = list(df[column].values)
    return dic

class DataBuffer:
    def __init__(self, symbol: str, timeframe: str, df: pd.DataFrame, technical_params: dict):
        self.symbol = symbol
        self.timeframe = timeframe        
        self.data = df2dic(df, 'time', COLUMNS)
        add_indicators(self.data, technical_params)

    def update(self, df: pd.DataFrame):
        dic = df2dic(df, 'time', COLUMNS)
        n = len(dic['time'])
        for timeframe, value in self.data.items():
            if timeframe in dic.keys():
                d = dic[timeframe]
                value += d
            else:
                value += nans(n)

