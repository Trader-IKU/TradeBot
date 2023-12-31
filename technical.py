import numpy as np 
import math
import statistics as stat
from mt5_trade import Columns
from common import Indicators, Signal, Columns, UP, DOWN
from datetime import datetime, timedelta

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
    def __init__(self, signal: Signal, time, price: float, stoploss: float, takeprofit: float, timelimit_minutes: int):
        self.signal = signal
        self.open_time = time
        self.open_price = price
        self.stoploss = stoploss
        self.takeprofit = takeprofit
        self.close_time = None
        self.close_price = None
        self.profit = None
        self.losscutted = False
        self.profittaken = False
        self.timelimit_minutes = int(timelimit_minutes)
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
                profit_high = high - self.open_price
                profit_low = low - self.open_price
                if profit_high >= self.takeprofit:
                    self.close(time, self.takeprofit)
                    self.profittaken = True
            elif self.signal == Signal.SHORT:
                profit_high = self.open_price - high
                profit_low = self.open_price - low
                if profit_low <= -1 * self.takeprofit:
                    self.close(time, self.takeprofit)
                    self.profittaken = True
                
    def timeup(self, time, high, low):
        if self.timelimit_minutes == 0:
            return
        if time <= (self.open_time + timedelta(minutes=self.timelimit_minutes)):
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

def supertrend_trade(data: dict, atr_window: int, sl_type: int, stoploss: float, tp_type: int, risk_reward: float, entry_horizon: int, exit_horizon: int, timeup_minutes: int, inverse: int):
    atr_window = int(atr_window)
    sl_type = int(sl_type)
    stoploss = float(stoploss)
    tp_type = int(tp_type)
    risk_reward = float(risk_reward)
    entry_horizon = int(entry_horizon)
    exit_horizon = int(exit_horizon)
    
    time = data[Columns.TIME]
    hi = data[Columns.HIGH]
    lo = data[Columns.LOW]
    cl = data[Columns.CLOSE]
    
    n = len(cl)
    signal = nans(n)
    super_upper = data[Indicators.SUPERTREND_U]
    super_lower = data[Indicators.SUPERTREND_L]
    trend = data[Indicators.SUPERTREND]   
    trades = []
    for i in range(1, n - 3):
        
        # ロスカット、利益確定、タイムリミット
        for tr in trades:
            tr.losscut(time[i], data[Columns.HIGH][i], data[Columns.LOW][i])    
            tr.take(time[i], data[Columns.HIGH][i], data[Columns.LOW][i])
            tr.timeup(time[i], data[Columns.HIGH][i], data[Columns.LOW][i])
                
        if trend[i - 1] == UP and trend[i] == DOWN:
            #if delta[i - 1] > tolerance:
            if inverse > 0:
                signal[i] = Signal.LONG
            else:
                signal[i] = Signal.SHORT
        elif trend[i - 1] == DOWN and trend[i] == UP:
            #if delta[i - 1] > tolerance:
            if inverse > 0:
                signal[i] = Signal.SHORT
            else:
                signal[i] = Signal.LONG

        l1 = i + entry_horizon
        l2 = i + exit_horizon
        if l1 >= n or l2 >= n:
            break

        if signal[i] == Signal.LONG:
            for tr in trades:
                if tr.not_closed():
                    tr.close(time[i], cl[i + exit_horizon])
            if sl_type == 0:
                # No stoploss
                stoploss = 0
            elif sl_type == 1:
                # Fix
                pass
            elif sl_type == 2:
                # Minimum value for atr window
                stoploss = cl[i + entry_horizon] - min(lo[i + entry_horizon - atr_window + 1: i + entry_horizon + 1])
            else:
                raise Exception('Bad stoploss type ' + str(sl_type))
            if tp_type == 0:
                # No takeprofit
                takeprofit = 0
            elif tp_type == 1:
                takeprofit = stoploss * risk_reward
            else:
                raise Exception('Bad takeprofit type ' + str(tp_type))
            trade = Trade(Signal.LONG, time[i], cl[i + entry_horizon], stoploss, takeprofit, timeup_minutes)
            trades.append(trade)
        elif signal[i] == Signal.SHORT:
            for tr in trades: 
                if tr.not_closed():
                    tr.close(time[i], cl[i + exit_horizon])
            if sl_type == 0:
                # No stoploss
                stoploss = 0
            elif sl_type == 1:
                #fix
                pass
            elif sl_type == 2:
                # Maximum value for atr window
                stoploss = max(lo[i + entry_horizon - atr_window + 1: i + entry_horizon + 1]) - cl[i + entry_horizon]
            else:
                raise Exception('Bad stoploss type ' + str(sl_type))
            if tp_type == 0:
                # No takeprofit
                takeprofit = 0
            elif tp_type == 1:
                takeprofit = stoploss * risk_reward
            else:
                raise Exception('Bad takeprofit type ' + str(tp_type))
            trade = Trade(Signal.SHORT, time[i], cl[i + entry_horizon], stoploss, takeprofit, timeup_minutes)                    
            trades.append(trade)               
    return trades 
    
def add_indicators(data: dict, params):
    cl = data[Columns.CLOSE]
    MA(data, Columns.CLOSE, params[Indicators.MA]['window'])
    TR(data)
    volatility(data, params[Indicators.VOLATILITY]['window'])
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
    

