import pandas as pd
import numpy as np
from mt5_trade import Mt5Trade, TimeFrame, Columns, nptimestamp2pydatetime
from datetime import datetime, timedelta
from common import Signal, Indicators
from technical import add_indicators, supertrend_trade



from dateutil import tz

JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc') 

COLUMNS = [Columns.TIME, Columns.OPEN, Columns.HIGH, Columns.LOW, Columns.CLOSE, 'tick_volume']
TICK_COLUMNS = [Columns.TIME, Columns.ASK, Columns.BID]

def nans(length):
    return [np.nan for _ in range(length)]

def jst2utc(jst: datetime): 
    return jst.astimezone(UTC)

def utcstr2datetime(utc_str: str, format='%Y-%m-%d %H:%M:%S'):
    utc = datetime.strptime(utc_str, format)
    utc = utc.replace(tzinfo=UTC)
    return utc

def utc2jst(utc: datetime):
    jst = utc.astimezone(JST)       
    return jst

def to_pydatetime(times, utc_from: datetime, delta_hour_from_gmt):
    if utc_from is None:
        i_begin = 0
    else:
        i_begin = -1
    out = []
    for i, time in enumerate(times):
        if type(time) is str:
            utc = utcstr2datetime(time) - delta_hour_from_gmt
        else:
            server_time = nptimestamp2pydatetime(time)
            utc = server_time - delta_hour_from_gmt
            utc = utc.replace(tzinfo=UTC)
        if utc_from is None:
            out.append(utc)
        else:
            if utc > utc_from:
                if i_begin == -1:
                    i_begin = i
                out.append(utc)
    return (i_begin, len(out), out)
    
def df2dic(df: pd.DataFrame, time_column: str, columns, utc_from: datetime,  delta_hour_from_gmt:timedelta):
    if type(df) == pd.Series:
        return df2dic_one(df, time_column, columns, utc_from, delta_hour_from_gmt)
    i_from, n, utc = to_pydatetime(df[time_column], utc_from, delta_hour_from_gmt)
    if n == 0:
        return (0, {})    
    dic = {}
    dic[time_column] = utc
    jst = [utc2jst(t) for t in utc]
    dic[Columns.JST] = jst
    for column in columns:
        if column != time_column:
            array = list(df[column].values)  
            dic[column] = array[i_from:]
    return (n, dic)

def df2dic_one(df: pd.DataFrame, time_column: str, columns, utc_from: datetime, delta_hour_from_gmt):
    time = df[time_column]
    i_from, n, utc = to_pydatetime([time], utc_from, delta_hour_from_gmt)
    if n == 0:
        return (0, {})    
    dic = {}
    dic[time_column] = utc
    jst = [utc2jst(t) for t in utc]
    dic[Columns.JST] = jst
    for column in columns:
        if column != time_column:
            dic[column] = [df[column]]
    return (n, dic)

class DataBuffer:
    def __init__(self, symbol: str, timeframe: str, df: pd.DataFrame, technical_params: dict, delta_hour_from_gmt):
        self.symbol = symbol
        self.timeframe = timeframe        
        self.delta_hour_from_gmt  =  delta_hour_from_gmt 
        n, data = df2dic(df, Columns.TIME, COLUMNS, None, self.delta_hour_from_gmt)
        if n == 0:
            raise Exception('Error cannot get initail data')
        add_indicators(data, technical_params)
        self.data = data
        self.technical_params = technical_params

    def last_time(self):
        t_utc = self.data[Columns.TIME][-1]
        return t_utc
    
    def update(self, df: pd.DataFrame):
        last = self.last_time()
        n, dic = df2dic(df, Columns.TIME, COLUMNS, last, self.delta_hour_from_gmt)
        if n == 0:
            return 0
        for key, value in self.data.items():
            if key in dic.keys():
                d = dic[key]
                value += d
            else:
                value += nans(n)
        add_indicators(self.data, self.technical_params)
        return n
                
                
def save(data: dict, path: str):
    d = data.copy()
    d[Columns.TIME] = [str(t) for t in d[Columns.TIME]]
    d[Columns.JST] = [str(t) for t in d[Columns.JST]]
    df = pd.DataFrame(d)
    df.to_excel(path, index=False)   
    
    
def test():
    path = '../MarketData/Axiory/NIKKEI/M30/NIKKEI_M30_2023_06.csv'
    df = pd.read_csv(path)

    df1 = df.iloc[:1003, :]
    df2 = df.iloc[1003:, :]
    
    print(len(df))
    print(len(df1))
    print(len(df2))
    params= {'MA':{'window':60}, 'ATR': {'window': 9, 'multiply': 3.0}}
    buffer = DataBuffer('', 'M30', df1, params)
    buffer.update(df2)
    save(buffer.data, './debug/divided.xlsx')
    


if __name__ == '__main__':
    test()
    
       
