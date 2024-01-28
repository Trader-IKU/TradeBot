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
        
def supertrend_trade(data: dict, atr_window: int, sl_type: int, stoploss: float, tp_type: int, takeprofit: float, entry_hold: int, timeup_minutes: int, inverse: int):
    atr_window = int(atr_window)
    sl_type = int(sl_type)
    stoploss = float(stoploss)
    tp_type = int(tp_type)
    takeprofit = float(takeprofit)
    entry_hold = int(entry_hold)
    
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
    
    ATR(data, params[Indicators.ATR]['window'], params[Indicators.ATR]['multiply'])    
    return SUPERTREND(data)