import numpy as np 
import math
import statistics as stat
from mt5_trade import Columns
from common import Indicators, Signal, Columns, UP, DOWN, HIGH, LOW, HOLD
from datetime import datetime, timedelta
from utils import Utils
from dateutil import tz

JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc') 

    
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

def slope(signal: list, window: int, tolerance=0.0):
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


def pivot(vector: list, left_length: int, right_length: int, threshold: float):
    n = len(vector)
    high = nans(n)
    low = nans(n)
    state = full(0, n)
    for i in range(left_length + right_length, n):
        center = vector[i - right_length]
        left = vector[i - left_length - right_length: i - right_length]
        right = vector[i - right_length + 1: i + 1]
        if threshold is not None:
            if abs(center) < threshold:
                continue
        if center > max(left) and center > max(right):
            high[i - right_length] = center
            state[i - right_length] = HIGH
        elif center < min(left) and center < min(right):
            low[i - right_length] = center
            state[i - right_length] = LOW
    return high, low, state

def cross_value(vector: list, value):
    n = len(vector)
    up = nans(n)
    down = nans(n)
    cross = full(HOLD, n)
    for i in range(1, n):
        if vector[i - 1] < value and vector[i] >= value:
            up[i] = 1
            cross[i] = UP
        elif vector[i - 1] > value and vector[i] <= value:
            down[i] = 1
            cross[i] = DOWN
    return up, down, cross

def rate(ref, signal):
    n = len(ref)
    out = nans(n)
    for i in range(n):
        r = ref[i]
        s = signal[i]
        if is_nans(([r, s])):
            continue
        if r != 0.0:
            out[i] = s / r * 100.0
    return out    
    
def band_position(data, lower, center, upper):
    n = len(data)
    pos = full(0, n)
    for i in range(n):
        if is_nan(data[i]):
            continue 
        if data[i] > upper[i]:
            pos[i] = 2
        else:
            if data[i] > center[i]:
                pos[i] = 1
        if data[i] < lower[i]:
            pos[i] = -2
        else:
            if data[i] < center[i]:
                pos[i] = -1
    return pos

def probability(position, states, window):
    n = len(position)
    prob = full(0, n)
    for i in range(window - 1, n):
        s = 0
        for j in range(i - window + 1, i + 1):
            if is_nan(position[j]):
                continue
            for st in states:
                if position[j] == st:
                    s += 1
                    break
        prob[i] = float(s) / float(window) * 100.0 
    return prob      
        
def MA( dic: dict, column: str, window: int):
    name = Indicators.MA + str(window)
    vector = dic[column]
    d = moving_average(vector, window)
    dic[name] = d

    
def ATR(dic: dict, term: int, term_long:int):
    hi = dic[Columns.HIGH]
    lo = dic[Columns.LOW]
    cl = dic[Columns.CLOSE]
    term = int(term)
    tr = true_range(hi, lo, cl)
    dic[Indicators.TR] = tr
    atr = moving_average(tr, term)
    dic[Indicators.ATR] = atr
    if term_long is not None:
        atr_long = moving_average(tr, term_long)
        dic[Indicators.ATR_LONG] = atr_long

    
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
    data[Indicators.DX] = dx
    data[Indicators.ADX] = adx
    data[Indicators.DI_PLUS] = dip
    data[Indicators.DI_MINUS] = dim
    if adx_term_long is not None:
        adx_long = moving_average(dx, adx_term_long)
        data[Indicators.ADX_LONG] = adx_long
    
    
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
    
def BBRATE(data: dict, window: int, ma_window):
    cl = data[Columns.CLOSE]
    n = len(cl)
    std = nans(n)     
    for i in range(window - 1, n):
        d = cl[i - window + 1: i + 1]    
        std[i] = np.std(d)   
    ma = moving_average(cl, ma_window)     
    rate = nans(n)
    for i in range(n):
        c = cl[i]
        m = ma[i]
        s = std[i]
        if is_nans([c, m, s]):
            continue
        rate[i] = (cl[i] - ma[i]) / s * 100.0
    data[Indicators.BBRATE] = rate
    

def BB(data: dict, window: int, ma_window:int, band_multiply):
    cl = data[Columns.CLOSE]
    n = len(cl)
    #ro = roi(cl)
    std = nans(n)     
    for i in range(window - 1, n):
        d = cl[i - window + 1: i + 1]    
        std[i] = np.std(d)   
    ma = moving_average(cl, ma_window)     
        
    upper, lower = band(ma, std, band_multiply)    
    data[Indicators.BB] = std
    data[Indicators.BB_UPPER] = upper
    data[Indicators.BB_LOWER] = lower
    data[Indicators.BB_MA] = ma
    
    pos = band_position(cl, lower, ma, upper)
    up = probability(pos, [1, 2], 50)
    down = probability(pos, [-1, -2], 50)
    data[Indicators.BB_UP] = up
    data[Indicators.BB_DOWN] = down
    
    cross_up, cross_down, cross = cross_value(up, 50)
    data[Indicators.BB_CROSS] = cross
    data[Indicators.BB_CROSS_UP] = cross_up
    data[Indicators.BB_CROSS_DOWN] = cross_down

def time_jst(year, month, day, hour=0):
    t0 = datetime(year, month, day, hour)
    t = t0.replace(tzinfo=JST)
    return t

def VWAP(data: dict, multiply: float, begin_hour=7):
    def next(jst, begin, hour):
        n = len(jst)
        t = jst[begin]
        tref = time_jst(t.year, t.month, t.day, hour=hour)
        if tref < t:
            tref += timedelta(days=1)
        for i in range(begin, n):
            if jst[i] >= tref:
                return i
        return -1

    jst = data[Columns.JST]
    n = len(jst)
    begin = 0
    begin = next(jst, begin, begin_hour)
    if begin < 0:
        begin = 0
    end = next(jst, begin + 1, begin_hour)
    if end < 0: 
        end = n - 1
    
    MID(data)
    mid = data[Columns.MID]
    volume = data['tick_volume']
    
    vwap = full(0, n)
    power_acc = full(0, n)
    volume_acc = full(0, n)
    std = full(0, n)
    while begin < n:
        power_sum = 0
        vwap_sum = 0
        volume_sum = 0
        for i in range(begin, end):
            vwap_sum += volume[i] * mid[i]
            volume_sum += volume[i]  
            volume_acc[i] = volume_sum
            power_sum += volume[i] * mid[i] * mid[i]  
            if volume_sum > 0:
                vwap[i] = vwap_sum / volume_sum
                power_acc[i] = power_sum
                deviation = power_sum / volume_sum - vwap[i] * vwap[i]
                if deviation > 0:
                    std[i] = np.sqrt(deviation)
                else:
                    std[i] = 0
        begin = end
        end = next(jst, begin, begin_hour)
        if end < 0:
            break
    
    data[Indicators.VWAP] = vwap
    data[Indicators.VWAP_STD] = rate(vwap, std)
    data[Indicators.VWAP_SLOPE] = slope(vwap, 10)
    upper, lower = band(vwap, std, multiply)
    data[Indicators.VWAP_UPPER] = upper
    data[Indicators.VWAP_LOWER] = lower
    
    pos = band_position(mid, lower, vwap, upper)
    up = probability(pos, [1, 2], 50)
    down = probability(pos, [-1, -2], 50)
    data[Indicators.VWAP_UP] = up
    data[Indicators.VWAP_DOWN] = down

    cross_up, cross_down, cross = cross_value(up, 50)
    data[Indicators.VWAP_CROSS] = cross
    data[Indicators.VWAP_CROSS_UP] = cross_up
    data[Indicators.VWAP_CROSS_DOWN] = cross_down
    
    pass
    
    
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
    if len(values) == 0:
        return True
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
    
    
def ATR_TRAIL(data: dict, atr_window: int, atr_multiply: float, peak_hold_term: int):
    atr_window = int(atr_window)
    atr_multiply = int(atr_multiply)
    peak_hold_term = int(peak_hold_term)
    time = data[Columns.TIME]
    op = data[Columns.OPEN]
    hi = data[Columns.HIGH]
    lo = data[Columns.LOW]
    cl = data[Columns.CLOSE]
    n = len(cl)
    ATR(data, atr_window, None)
    atr = data[Indicators.ATR]
    stop = nans(n)
    for i in range(n):
        h = hi[i]
        a = atr[i]
        if is_nans([h, a]):
            continue
        stop[i] = h - a * atr_multiply
        
    trail_stop = nans(n)
    for i in range(n):
        d = stop[i - peak_hold_term + 1: i + 1]
        if is_nans(d):
            continue
        trail_stop[i] = max(d)
        
    trend = full(0, n)
    for i in range(n):
        c = cl[i]
        s = trail_stop[i]
        if is_nans([c, s]):
            continue
        if c > s:
            trend[i] = UP
        else:
            trend[i] = DOWN
            
    data[Indicators.ATR_TRAIL] = trail_stop
    data[Indicators.ATR_TRAIL_TREND] = trend
    
    up = nans(n)
    down = nans(n)
    for i in range(n):
        if trend[i] == UP:
            up[i] = trail_stop[i]    
        if trend[i] == DOWN:
            down[i] = trail_stop[i]
    data[Indicators.ATR_TRAIL_UP] = up
    data[Indicators.ATR_TRAIL_DOWN] = down
    
             
def SUPERTREND(data: dict,  multiply, column=Columns.MID):
    time = data[Columns.TIME]
    if column == Columns.MID:
        MID(data)
    price = data[column]
    n = len(time)
    atr_u, atr_l = band(data[column], data[Indicators.ATR], multiply)
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
    

