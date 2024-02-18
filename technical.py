import numpy as np 
import math
import statistics as stat
from mt5_trade import Columns
from common import Indicators, Signal, Columns, UP, DOWN
from datetime import datetime, timedelta


    
def nans(length):
    return [np.nan for _ in range(length)]

def full(value, length):
    return [value for _ in range(length)]

def moving_average(vector, window):
    window = int(window)
    n = len(vector)
    out = nans(n)
    ivalid = window- 1
    if ivalid < 0:
        return out
    for i in range(ivalid, n):
        d = vector[i - window + 1: i + 1]
        out[i] = stat.mean(d)
    return out

def slope(signal: list, window: int, tolerance=1e-5):
    n = len(signal)
    out = full(0, n)
    for i in range(window - 1, n):
        d = signal[i - window + 1: i + 1]
        m, offset = np.polyfit(range(window), d, 1)
        if abs(m) > tolerance:
            out[i] = m
    return out

def subtract(signal1: list, signal2:list):
    n = len(signal1)
    if len(signal2) != n:
        raise Exception('dont match list size')
    out = nans(n)
    for i in range(n):
        if is_nan(signal1[i]) or is_nan(signal2[i]):
            continue
        out[i] = signal1[i] - signal2[i]
    return out


def linearity(signal: list, window: int):
    n = len(signal)
    out = nans(n)
    for i in range(window, n):
        data = signal[i - window + 1: i + 1]
        if is_nans(data):
            continue
        m, offset = np.polyfit(range(window), data, 1)
        e = 0
        for j, d in enumerate(data):
            estimate = m * j + offset
            e += pow(estimate - d, 2)
        error = np.sqrt(e) / window / data[0] * 100.0
        if error == 0:
            out[i] = 100.0
        else:
            out[i] = 1 / error
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
    return out

def roi(vector:list):
    n = len(vector)
    out = nans(n)
    for i in range(1, n):
        if is_nan(vector[i - 1]) or is_nan(vector[i]):
            continue
        if vector[i - 1] == 0:
            out[i] = 0.0
        else:
            out[i] = (vector[i] - vector[i - 1]) / vector[i - 1] * 100.0
    return out

def MA(dic: dict, column: str, window: int):
    name = Indicators.MA + str(window)
    vector = dic[column]
    d = moving_average(vector, window)
    dic[name] = d

    
def ATR(dic: dict, term: int, term_long:int, band_multiply):
    hi = dic[Columns.HIGH]
    lo = dic[Columns.LOW]
    cl = dic[Columns.CLOSE]
    term = int(term)
    tr = true_range(hi, lo, cl)
    dic[Indicators.TR] = tr
    atr = moving_average(tr, term)
    atr_long = moving_average(tr, term_long)
    dic[Indicators.ATR] = atr
    dic[Indicators.ATR_LONG] = atr_long
    upper, lower = band(cl, atr, band_multiply)
    dic[Indicators.ATR_UPPER] = upper
    dic[Indicators.ATR_LOWER] = lower
    
def ADX(data: dict, di_window: int, adx_term: int, adx_term_long:int):
    hi = data[Columns.HIGH]
    lo = data[Columns.LOW]
    tr = data[Indicators.TR]
    n = len(hi)
    dmp = nans(n)     
    dmm = nans(n)     
    for i in range(1, n):
        p = hi[i]- hi[i - 1]
        m = lo[i - 1] - lo[i]
        dp = dn = 0
        if p >= 0 or n >= 0:
            if p > m:
                dp = p
            if p < m:
                dn = m
        dmp[i] = dp
        dmm[i] = dn
    dip = nans(n)
    dim = nans(n)
    dx = nans(n)
    for i in range(di_window - 1, n):
        s_tr = sum(tr[i - di_window + 1: i + 1])
        s_dmp = sum(dmp[i - di_window + 1: i + 1])
        s_dmm = sum(dmm[i - di_window + 1: i + 1])
        dip[i] = s_dmp / s_tr * 100 
        dim[i] = s_dmm / s_tr * 100
        dx[i] = abs(dip[i] - dim[i]) / (dip[i] + dim[i]) * 100
    adx = moving_average(dx, adx_term)
    adx_long = moving_average(dx, adx_term_long)
    
    data[Indicators.DX] = dx
    data[Indicators.ADX] = adx
    data[Indicators.ADX_LONG] = adx_long
    data[Indicators.DI_PLUS] = dip
    data[Indicators.DI_MINUS] = dim

    
def POLARITY(data: dict, window: int):
    hi = data[Columns.HIGH]
    lo = data[Columns.LOW]
    tr = data[Indicators.TR]
    n = len(hi)
    dmp = nans(n)     
    dmm = nans(n)     
    for i in range(1, n):
        p = hi[i]- hi[i - 1]
        m = lo[i - 1] - lo[i]
        dp = dn = 0
        if p >= 0 or n >= 0:
            if p > m:
                dp = p
            if p < m:
                dn = m
        dmp[i] = dp
        dmm[i] = dn
    dip = nans(n)
    dim = nans(n)
    for i in range(window - 1, n):
        s_tr = sum(tr[i - window + 1: i + 1])
        s_dmp = sum(dmp[i - window + 1: i + 1])
        s_dmm = sum(dmm[i - window + 1: i + 1])
        dip[i] = s_dmp / s_tr * 100 
        dim[i] = s_dmm / s_tr * 100
    
    di = subtract(dip, dim)
    pol = nans(n)
    for i in range(n):
        if is_nan(di[i]):
            continue
        if di[i] > 0:
            pol[i] = UP
        elif di[i] < 0:
            pol[i] = DOWN
    data[Indicators.POLARITY] = pol  
    

def STDEV(data: dict, term: int, term_long:int, band_multiply):
    cl = data[Columns.CLOSE]
    n = len(cl)
    ro = roi(cl)
    std = nans(n)     
    for i in range(term - 1, n):
        d = ro[i - term + 1: i + 1]    
        std[i] = np.std(d)   
    std_long = nans(n)     
    for i in range(term_long - 1, n):
        d = ro[i - term_long + 1: i + 1]    
        std_long[i] = np.std(d)     
        
    upper, lower = band(cl, std, band_multiply)    
    data[Indicators.STDEV] = std
    data[Indicators.STDEV_UPPER] = upper
    data[Indicators.STDEV_LOWER] = lower
    data[Indicators.STDEV_LONG] = std_long
    
def band(vector, signal, multiply):
    n = len(vector)
    upper = nans(n)
    lower = nans(n)
    for i in range(n):
        upper[i] = vector[i] + multiply * signal[i]
        lower[i] = vector[i] - multiply * signal[i]
    return upper, lower

def is_nan(value):
    if value is None:
        return True
    return np.isnan(value)

def is_nans(values):
    for value in values:
        if is_nan(value):
            return True
    return False

def volatility(data: dict, window: int):
    time = data[Columns.TIME]
    op = data[Columns.OPEN]
    hi = data[Columns.HIGH]
    lo = data[Columns.LOW]
    cl = data[Columns.CLOSE]
    n = len(cl)
    volatile = nans(n)
    for i in range(window, n):
        d = []
        for j in range(i - window + 1, i + 1):
            d.append(cl[j - 1] - op[j])
            if cl[j] > op[j]:
                # positive
                d.append(lo[j] - op[j])
                d.append(hi[j] - lo[j])
                d.append(cl[j] - hi[j])
            else:
                d.append(hi[j] - op[j])
                d.append(lo[j] - hi[j])
                d.append(cl[j] - lo[j])
        sd = stat.stdev(d)
        volatile[i] = sd / float(window) / op[i] * 100.0
    return               
            
def TREND_ADX_DI(data: dict, adx_threshold: float):
    adx = data[Indicators.ADX]
    adx_slope = slope(adx, 5)
    di_p = data[Indicators.DI_PLUS]
    di_m = data[Indicators.DI_MINUS]
    n = len(adx)
    trend = full(0, n)
    for i in range(n):
        if adx[i] > adx_threshold and adx_slope[i] > 0: 
            delta = di_p[i] - di_m[i]
            if delta > 0:
                trend[i] = UP
            elif delta < 0:
                trend[i] = DOWN
    data[Indicators.TREND_ADX_DI] = trend

def MID(data: dict):
    if Columns.MID in data.keys():
        return
    cl = data[Columns.CLOSE]
    op = data[Columns.OPEN]
    n = len(cl)
    md = nans(n)
    for i in range(n):
        o = op[i]
        c = cl[i]
        if is_nans([o, c]):
            continue
        md[i] = (o + c) / 2
    data[Columns.MID] = md
             
def SUPERTREND(data: dict, column=Columns.MID):
    time = data[Columns.TIME]
    if column == Columns.MID:
        MID(data)
    price = data[column]
    n = len(time)
    atr_u = data[Indicators.ATR_UPPER]
    atr_l = data[Indicators.ATR_LOWER]
    trend = nans(n)
    super_upper = nans(n)
    super_lower = nans(n)
    is_valid = False
    for i in range(1, n):
        if is_valid == False:
            if is_nans([atr_l[i - 1], atr_u[i - 1]]):
                continue
            else:
                super_lower[i - 1] = atr_l[i - 1]
                trend[i - 1] = UP
                is_valid = True            
        if trend[i - 1] == UP:
            # up trend
            if np.isnan(super_lower[i - 1]):
                super_lower[i] = atr_l[i -1]
            else:
                if atr_l[i] > super_lower[i - 1]:
                    super_lower[i] = atr_l[i]
                else:
                    super_lower[i] = super_lower[i - 1]
            if price[i] < super_lower[i]:
                # up->down trend 
                trend[i] = DOWN
            else:
                trend[i] = UP
        else:
            # down trend
            if np.isnan(super_upper[i - 1]):
                super_upper[i] = atr_u[i]
            else:
                if atr_u[i] < super_upper[i - 1]:
                    super_upper[i] = atr_u[i]
                else:
                    super_upper[i] = super_upper[i - 1]
            if price[i] > super_upper[i]:
                # donw -> up trend
                trend[i] = UP
            else:
                trend[i] = DOWN
           
    data[Indicators.SUPERTREND_UPPER] = super_upper
    data[Indicators.SUPERTREND_LOWER] = super_lower
    data[Indicators.SUPERTREND] = trend    
    return 

def diff(data: dict, column: str):
    signal = data[column]
    time = data[Columns.TIME]
    n = len(signal)
    out = nans(n)
    for i in range(1, n):
        dt = time[i] - time[i - 1]
        out[i] = (signal[i] - signal[i - 1]) / signal[i - 1] / (dt.seconds / 60) * 100.0
    return out





def test():
    sig = [1, 2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    ma = full(-1, len(sig))
    
    moving_average(sig, ma, 2, 5)
    print(ma)
    
if __name__ == '__main__':
    test()
    

