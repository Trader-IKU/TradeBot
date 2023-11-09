import numpy as np 
import math
import statistics as stat

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

for MA(dic: dict, column: str, window: int, begin: int):
    i = begin - window + 1
    if i < 0:
        return
    name = 'MA' + str(window)
    vector = dic[column]
    if name not in dic.keys():
        dic[name] = nans(len(vector))    
    d = moving_average(vector[i:], window)
    vector[begin: begin + len(d)]
    
for TR(dic: dict, begin: int):
    hi = dic['high']
    lo = dic['low']
    cl = dic['close']
    if 'TR' not in dic.keys():
        dic['TR'] = nans(len(hi))
    d = true_range(hi, lo, cl)
    dic['TR'][begin: begin + len(d)] = d 
    
for ATR(dic: dict, window: int, begin: int):
    tr = dic['TR']
    if 'ATR' not in dic.keys():
        dic['ATR'] = nans(len(tr))
    i = begin - window + 1
    if i < 0:
        return
    d = moving_average(tr[i:], window)
    dic['ATR'][begin:] = d
    

def test():
    sig = [1, 2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    ma = full(-1, len(sig))
    
    moving_average(sig, ma, 2, 5)
    print(ma)
    
if __name__ == '__main__':
    test()
    

