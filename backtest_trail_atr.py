import os
import sys
sys.path.append('../Libraries/trade')

from technical import *
from backtest import Optimize, TradeBotSim


def indicators(data: dict, param: dict):
    atr_window = param['atr_window']
    atr_multiply = param['atr_multiply']
    peak_hold_term = param['peak_hold_term']
    ATR_TRAIL(atr_window, atr_multiply, peak_hold_term)
    
class TradeBotSimTrailATR(TradeBotSim):
    def detect_entry(self, data: dict):
        trend = data[Indicators.ATR_TRAIL_TREND]
        long_patterns = [[DOWN, UP], [0, UP]]
        short_patterns = [[UP, DOWN], [0, DOWN]]
        d = trend[-2:]
        for pat in long_patterns:
            if d == pat:
                return Signal.LONG
        for pat in short_patterns:
            if d == pat:
                return Signal.SHORT
        return None
    

def main():
    args = sys.argv
    if len(args) < 2:
        #raise Exception('Bad parameter')
        # for debug
        args = ['', 'NIKKEI', 'H4']
    if len(args) < 4:
        number = 0
    else:
        number = int(args[3])
        
    symbol = args[1]
    symbol = symbol.upper()
    timeframe = args[2]
    timeframe = timeframe.upper()
    if symbol == 'FX':
        symbols =  ['USDJPY', 'EURJPY', 'EURUSD', 'GBPJPY', 'AUDJPY']
    elif symbol == 'STOCK':
        symbols = ['NIKKEI', 'DOW', 'NSDQ', 'HK50']
    elif symbol == 'COMODITY':
        symbols =  ['XAUUSD', 'CL']
    else:
        symbols = [symbol]
        
    for symbol in symbols:
        optimize = Optimize(symbol, timeframe, indicators, TradeBotSimTrailATR)
        if optimize.load_data(2020, 1, 2020, 3):
            optimize.run(number)
        else:
            print(symbol + ": No data")
               
if __name__ == '__main__':
    main()