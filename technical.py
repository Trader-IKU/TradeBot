import numpy as np 
import math
import statistics as stat
from mt5_trade import Columns
from common import Indicators, Signal, Columns, UP, DOWN, DOWN_TO_UP, UP_TO_DOWN
from datetime import datetime, timedelta

SlTpType = int
SL_TP_TYPE_NONE: SlTpType = 0
SL_TP_TYPE_FIX: SlTpType = 1
SL_TP_TYPE_AUTO: SlTpType = 2

def trade_summary(trades):
    n = len(trades)
    s = 0
    minv = maxv = None
    win_count = 0
    for trade in trades:
        if trade.profit is None:
            continue
        s += trade.profit
        if trade.profit > 0:
            win_count += 1
        if minv is None:
            minv = maxv = s
        else:
            if s < minv:
                minv = s
            if s > maxv:
                maxv = s
    if n > 0:
        rates = float(win_count) / float(n)
    else:
        rates = 0.0
    return n, s, minv, maxv, rates
    
class Trade:
    def __init__(self, id: int, signal: Signal, time, count, price: float, stoploss: float, takeprofit: float, timelimit: int):
        self.id = id
        self.signal = signal
        self.open_time = time
        self.open_count = count
        self.open_price = price
        self.stoploss = stoploss
        self.takeprofit = takeprofit
        self.close_time = None
        self.close_price = None
        self.profit = None
        self.losscutted = False
        self.profittaken = False
        self.timelimit = int(timelimit)
        self.time_upped = False
        
    def close(self, time, price):
        self.close_time = time
        self.close_price = price
        self.profit = self.close_price - self.open_price
        if self.signal == Signal.SHORT:
            self.profit *= -1.0
 
    def losscut(self, time, high, low):
        if self.not_closed():
            if self.signal == Signal.LONG:
                profit = low - self.open_price
                if profit <= -1 * self.stoploss:
                    self.close(time, low)
                    self.losscutted = True
            elif self.signal == Signal.SHORT:
                profit = self.open_price - high
                if profit <= -1 * self.stoploss:
                    self.close(time, high)
                    self.losscutted = True
    
    def take(self, time, high, low):
        if self.takeprofit == 0:
            return
        if self.not_closed():
            if self.signal == Signal.LONG:
                profit = high - self.open_price
                if profit >= self.takeprofit:
                    self.close(time, high)
                    self.profittaken = True
            elif self.signal == Signal.SHORT:
                profit = self.open_price - low
                if profit >=  self.takeprofit:
                    self.close(time, low)
                    self.profittaken = True
                
    def timeup(self, time, count, high, low):
        if self.timelimit == 0:
            return
        if count < (self.open_count + self.timelimit):
            return
        if self.not_closed():
            if self.signal == Signal.LONG:
                self.close(time, low)
                self.time_upped = True
            elif self.signal == Signal.SHORT:
                self.close(time, high)
                self.time_upped = True           
                
    def not_closed(self):
        return (self.profit is None)
    
    def array(self):
        if self.signal == Signal.LONG:
            signal = 'Long'
        else:
            signal = 'Short'
        data = [self.open_time, self.open_price, signal, self.close_time, self.close_price, self.profit]
        columns = ['OpenTime', 'OpenPrice', 'Signal', 'CloseTime', 'ClosePrice', 'Profit']
        return data, columns
    
    def desc(self):
        print(self.signal, 'open:', self.open_time, self.open_price, 'close:', self.close_time, self.close_price, self.profit)
    
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

def moving_average_bug(vector, window):
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
    return out

def MA(dic: dict, column: str, window: int):
    name = Indicators.MA + str(window)
    vector = dic[column]
    d = moving_average(vector, window)
    dic[name] = d

def TR(dic: dict):
    hi = dic[Columns.HIGH]
    lo = dic[Columns.LOW]
    cl = dic[Columns.CLOSE]
    d = true_range(hi, lo, cl)
    dic[Indicators.TR] = d 
    
def ATR(dic: dict, window: int):
    window = int(window)
    tr = dic[Indicators.TR]
    d = moving_average(tr, window)
    dic[Indicators.ATR] = d
    
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
    data[Indicators.VOLATILITY] = volatile
    return               
             
def supertrend(data: dict):
    time = data[Columns.TIME]
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
            if cl[i] < super_lower[i]:
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
            if cl[i] > super_upper[i]:
                # donw -> up trend
                trend[i] = UP
            else:
                trend[i] = DOWN
           
    data[Indicators.SUPERTREND_U] = super_upper
    data[Indicators.SUPERTREND_L] = super_lower
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


def check_signal(trend: list, i: int, entry_hold: int, inverse: bool):
    long_pattern = [DOWN, UP]
    short_pattern = [UP, DOWN]
    for _ in range(entry_hold):
        long_pattern.append(UP)
        short_pattern.append(DOWN)            
    d = trend[i - (entry_hold + 1): i + 1]

    if d == long_pattern:
        sig = Signal.LONG
    elif d == short_pattern:
        sig = Signal.SHORT
    else:
        sig = None
    if inverse > 0:
        if sig == Signal.SHORT:
            sig = Signal.LONG
        elif sig == Signal.LONG:
            sig = Signal.SHORT
    return sig

def check_reversal(trend: list, i: int):
    if trend[i - 1] == DOWN and trend[i] == UP:
        return DOWN_TO_UP
    elif trend[i - 1] == UP and trend[i] == DOWN:
        return UP_TO_DOWN
    return None

def calc_stoploss(op, hi, lo, cl, i, window, signal):
    if signal == Signal.LONG:
        d = lo[i - window - 1 : i + 1]
        return min(d)
    elif signal == Signal.SHORT:
        d = hi[i - window - 1: i + 1]
        return max(d)

def reversal_close(trades, time, price):
    for trade in trades:
        if trade.not_closed():
            trade.close(time, price)

def supertrend_trade(data: dict, atr_window: int, sl_type: int, stoploss: float, tp_type: int, takeprofit: float, entry_hold: int, exit_hold: int, timeup_minutes: int, inverse: int):
    atr_window = int(atr_window)
    sl_type = int(sl_type)
    stoploss = float(stoploss)
    tp_type = int(tp_type)
    takeprofit = float(takeprofit)
    entry_hold = int(entry_hold)
    exit_hold = int(exit_hold)
    
    time = data[Columns.TIME]
    op = data[Columns.OPEN]
    hi = data[Columns.HIGH]
    lo = data[Columns.LOW]
    cl = data[Columns.CLOSE]
    
    n = len(cl)
    signal = nans(n)
    reversal = nans(n)
    trend = data[Indicators.SUPERTREND]   
    trades = []
    for i in range(entry_hold, n):
        # ロスカット、利益確定、タイムリミット
        for tr in trades:
            if sl_type != SL_TP_TYPE_NONE:
                tr.losscut(time[i], data[Columns.HIGH][i], data[Columns.LOW][i])  
            if tp_type != SL_TP_TYPE_NONE:
                tr.take(time[i], data[Columns.HIGH][i], data[Columns.LOW][i])
            if timeup_minutes > 0:
                tr.timeup(time[i], i, data[Columns.HIGH][i], data[Columns.LOW][i])

        sig = check_signal(trend, i, entry_hold, inverse)
        signal[i] = sig
        rev = check_reversal(trend, i)
        reversal[i] = rev
        if tp_type == SL_TP_TYPE_NONE and (rev == DOWN_TO_UP or rev == UP_TO_DOWN) :
            #ドテン
            reversal_close(trades, time[i], cl[i])
            
        if sig == Signal.LONG:
            if sl_type == SL_TP_TYPE_NONE:
                # No stoploss
                stoploss = 0
            elif sl_type == SL_TP_TYPE_AUTO:
                # Minimum value for atr window
                stoploss = calc_stoploss(op, hi, lo, cl, i, 5, sig)
            elif sl_type == SL_TP_TYPE_FIX:
                # Fix
                pass
            else:
                raise Exception('Bad stoploss type ' + str(sl_type))
            if tp_type == SL_TP_TYPE_NONE:
                # No takeprofit
                takeprofit = 0
            elif tp_type == SL_TP_TYPE_FIX:
                # Fix
                pass
            else:
                raise Exception('Bad takeprofit type ' + str(tp_type))
            trade = Trade(len(trades), Signal.LONG, time[i], i, cl[i], stoploss, takeprofit, timeup_minutes)
            trades.append(trade)
        elif sig == Signal.SHORT:
            if sl_type == SL_TP_TYPE_NONE:
                # No stoploss
                stoploss = 0
            elif sl_type == SL_TP_TYPE_AUTO:
                # Maximum value for atr window
                stoploss = calc_stoploss(op, hi, lo, cl, i, 5, sig)
            elif sl_type == SL_TP_TYPE_FIX:
                #fix
                pass
            else:
                raise Exception('Bad stoploss type ' + str(sl_type))
            if tp_type == SL_TP_TYPE_NONE:
                # No takeprofit
                takeprofit = 0
            elif tp_type == SL_TP_TYPE_FIX:
                # 
                pass
            else:
                raise Exception('Bad takeprofit type ' + str(tp_type))
            trade = Trade(len(trades), Signal.SHORT, time[i], i, cl[i], stoploss, takeprofit, timeup_minutes)                    
            trades.append(trade)               
    return trades 
    
def add_indicators(data: dict, params):
    cl = data[Columns.CLOSE]
    #MA(data, Columns.CLOSE, params[Indicators.MA]['window'])
    #volatility(data, params[Indicators.VOLATILITY]['window'])
    TR(data)
    
    ATR(data, params[Indicators.ATR]['window'])
    upper, lower = band(cl, data[Indicators.ATR], params[Indicators.ATR]['multiply'])    
    data[Indicators.ATR_U] = upper
    data[Indicators.ATR_L] = lower
    return supertrend(data)

def test():
    sig = [1, 2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    ma = full(-1, len(sig))
    
    moving_average(sig, ma, 2, 5)
    print(ma)
    
if __name__ == '__main__':
    test()
    

