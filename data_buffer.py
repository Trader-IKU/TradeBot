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

class DataBuffer:
    def __init__(self, symbol: str, timeframe: str, df: pd.DataFrame, technical_params: dict):
        self.symbol = symbol
        self.timeframe = timeframe        
        self.data = self.df2dic(df, Columns.TIME, COLUMNS, None)
        add_indicators(self.data, technical_params)

    def last_time(self):
        t_utc = self.data[Columns.TIME][-1]
        return t_utc
    
    def update(self, df: pd.DataFrame):
        n, dic = self.df2dic(df, Columns.TIME, COLUMNS)
        for key, value in self.data.items():
            if key in dic.keys():
                d = dic[key]
                value += d
            else:
                value += nans(n)
       
    def np2pydatetime(self, times, utc_from: datetime):
        i_begin = -1
        out = []
        for i, time in enumerate(times):
            dt = npdatetime2datetime(time) #numpy timestamp -> local datetime
            utc = dt.astimezone(UTC)
            if utc > utc_from:
                if i_begin == -1:
                    i_begin = i
                out.append(utc)
        return (i_begin, len(out), out)
       
    def df2dic(self, df: pd.DataFrame, time_column: str, columns, utc_from: datetime):
        i_from, n, utc = self.np2pydatetime(df[time_column], utc_from)
        if n == 0:
            return (0, {})    
        dic = {}
        dic[column] = utc
        jst = [utc2jst(t) for t in utc]
        dic[Columns.JST] = jst
        for column in columns:
            if column != time_column:
                array = list(df[column].values)  
                dic[column] = array[i_from:]
        return (n, dic)