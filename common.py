# -*- coding: utf-8 -*-
"""
Created on Thu Dec 14 19:59:00 2023

@author: docs9
"""
import MetaTrader5 as mt5


DOWN = -1
UP = 1
DOWN_TO_UP = 2
UP_TO_DOWN = 3
LOW = -1
HIGH = 1

class Columns:
    TIME = 'time'
    JST = 'jst'
    OPEN = 'open'
    HIGH = 'high'
    LOW = 'low'
    CLOSE = 'close'    
    ASK = 'ask'
    BID = 'bid'
    MID = 'mid'

class TimeFrame:
    TICK = 'TICK'
    M1 = 'M1'
    M5 = 'M5'
    M15 = 'M15'
    M30 = 'M30'
    H1 = 'H1'
    H4 = 'H4'
    D1 = 'D1'
    W1 = 'W1'
    
    timeframes = {  M1: mt5.TIMEFRAME_M1, 
                    M5: mt5.TIMEFRAME_M5,
                    M15: mt5.TIMEFRAME_M15,
                    M30: mt5.TIMEFRAME_M30,
                    H1: mt5.TIMEFRAME_H1,
                    H4: mt5.TIMEFRAME_H4,
                    D1: mt5.TIMEFRAME_D1,
                    W1: mt5.TIMEFRAME_W1}
            
    @staticmethod 
    def const(timeframe_str: str):
        return TimeFrame.timeframes[timeframe_str]

class Indicators:
    MA = 'MA'
    TR = 'TR'
    ATR = 'ATR'
    ATR_LONG = 'ATR_LONG'
    ATR_UPPER = 'ATR_UPPER'
    ATR_LOWER = 'ATR_LOWER'
    DX = 'DX'
    ADX = 'ADX'
    ADX_LONG = 'ADX_LONG'
    DI_PLUS = 'DI_PLUS'
    DI_MINUS = 'DI_MINUS'
    POLARITY = 'POLARITY'
    
    ATR_TRAIL = 'ATR_TRAIL'
    ATR_TRAIL_TREND = 'ATR_TRAIL_TREND'
    ATR_TRAIL_UP = 'ATR_TRAIL_UP'
    ATR_TRAIL_DOWN = 'ATR_TRAIL_DOWN'
    
    SUPERTREND_UPPER = 'SUPERTREND_U'
    SUPERTREND_LOWER = 'SUPERTREND_L'
    SUPERTREND = 'SUPERTREND'
    STDEV = 'STDEV'
    STDEV_MA = 'STDEV_MA'
    STDEV_UPPER = 'STDEV_UPPER'
    STDEV_LOWER = 'STDEV_LOWER'
    TREND_ADX_DI ='TREND_ADX_DI'
    
    BBRATE = 'BBRATE'

class Signal:
    LONG = 1
    SHORT = -1    