import numpy as np 
import math
import statistics as stat
from mt5_trade import Columns


class Indicators:
    MA = 'MA'
    TR = 'TR'
    ATR = 'ATR'
    ATR_U = 'ATR_U'
    ATR_L = 'ATR_L'
    SUPERTREND_U = 'SUPERTREND_U'
    SUPERTREND_L = 'SUPERTREND_L'
    SUPERTREND = 'SUPERTREND'

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

def is_nan(values):
    for value in values:
        if np.isnan(value):
            return True
    return False
             
def supertrend(data: dict):
    cl = data[Columns.CLOSE]
    atr_u = data[Indicators.ATR_U]
    atr_l = data[Indicators.ATR_L]
    n = len(cl)
    trend = nans(n)
    super_upper = nans(n)
    super_lower = nans(n)
    is_valid = False
    for i in range(1, n):
        if is_valid == False:
            if is_nan([atr_l[i - 1], atr_u[i - 1]]):
                continue
            else:
                super_lower[i - 1] = atr_l[i - 1]
                trend[i - 1] = 1
                is_valid = True            
        if trend[i - 1] == 1:
            # up trend
            if np.isnan(super_lower[i - 1]):
                super_lower[i] = atr_l[i -1]
            else:
                if atr_l[i] > super_lower[i - 1]:
                    super_lower[i] = atr_l[i]
                else:
                    super_lower[i] = super_lower[i - 1]
            if cl[i] < super_lower[i]:
                # up->down trend 
                trend[i] = 0
            else:
                trend[i] = 1
        else:
            # down trend
            if np.isnan(super_upper[i - 1]):
                super_upper[i] = atr_u[i]
            else:
                if atr_u[i] < super_upper[i - 1]:
                    super_upper[i] = atr_u[i]
                else:
                    super_upper[i] = super_upper[i - 1]
            if cl[i] > super_upper[i]:
                # donw -> up trend
                trend[i] = 1
            else:
                trend[i] = 0
    data[Indicators.SUPERTREND_U] = super_upper
    data[Indicators.SUPERTREND_L] = super_lower
    data[Indicators.SUPERTREND] = trend    
     
def indicators(data: dict):
    cl = data[Columns.CLOSE]
    
    MA(data, Columns.CLOSE, 9, 8)
    TR(data, 1)
    ATR(data, 5, 4)
    upper, lower = band(cl, data[Indicators.ATR], 2.0)    
    data[Indicators.ATR_U] = upper
    data[Indicators.ATR_L] = lower
    supertrend(data)


def test():
    sig = [1, 2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    ma = full(-1, len(sig))
    
    moving_average(sig, ma, 2, 5)
    print(ma)
    
if __name__ == '__main__':
    test()
    

