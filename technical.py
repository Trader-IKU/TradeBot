import numpy as np 
import math
import statistics as stat
from mt5_trade import Columns


class Indicators:
    MA = 'MA'
    TR = 'TR'
    ATR = 'ATR'
    ATR_U = 'ATR_u'
    ATR_D = 'ATR_d'
    SUPERTREND_U = 'SUPERTREND_u'
    SUPERTREND_D = 'SUPERTREND_d'

def nans(length):
    return [np.nan for _ in range(length)]

def full(value, length):
    return [value for _ in range(length)]

def moving_average(vector,window):
    n = len(vector)
    out = nans(n)
    ivalid = window - 1
    if ivalid < 0:
        return out
    for i in range(ivalid, n):
        d = vector[i: i + window]
        out[i] = stat.mean(d)
    return out

def true_range(high, low, cl):
    n = len(high)
    out = nans(n)
    ivalid = 1
    for i in range(ivalid, n):
        d = [ high[i] - low[i],
              abs(high[i] - cl[i - 1]),
              abs(low[i] - cl[i - 1])]
        out[i] = max(d)
    return out[ivalid:]

def MA(dic: dict, column: str, window: int, begin: int):
    i = begin - window + 1
    if i < 0:
        return
    name = Indicators.MA + str(window)
    vector = dic[column]
    if name not in dic.keys():
        dic[name] = nans(len(vector))    
    d = moving_average(vector[i:], window)
    vector[begin: begin + len(d)]
    
def TR(dic: dict, begin: int):
    hi = dic[Columns.HIGH]
    lo = dic[Columns.LOW]
    cl = dic[Columns.CLOSE]
    if Indicators.TR not in dic.keys():
        dic[Indicators.TR] = nans(len(hi))
    d = true_range(hi, lo, cl)
    dic[Indicators.TR][begin: begin + len(d)] = d 
    
def ATR(dic: dict, window: int, begin: int):
    tr = dic[Indicators.TR]
    if Indicators.ATR not in dic.keys():
        dic[Indicators.ATR] = nans(len(tr))
    i = begin - window + 1
    if i < 0:
        return
    d = moving_average(tr[i:], window)
    dic[Indicators.ATR][begin:] = d
    
def band(vector, signal, multiply):
    n = len(vector)
    upper = nans(n)
    lower = nans(n)
    for i in range(n):
        upper[i] = vector[i] + multiply * signal[i]
        lower[i] = vector[i] - multiply * signal[i]
    return upper, lower
     
def indicators(data: dict):
    time = data[Columns.TIME]
    op = data[Columns.OPEN]
    hi = data[Columns.HIGH]
    lo = data[Columns.LOW]
    cl = data[Columns.CLOSE]
    
    MA(data, Columns.CLOSE, 9, 8)
    TR(data, 1)
    ATR(data, 5, 4)
    upper, lower = band(cl, data[Indicators.ATR], 2.0)    
    data[Indicators.ATR_U] = upper
    data[Indicators.ATR_D] = lower    


def test():
    sig = [1, 2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    ma = full(-1, len(sig))
    
    moving_average(sig, ma, 2, 5)
    print(ma)
    
if __name__ == '__main__':
    test()
    

