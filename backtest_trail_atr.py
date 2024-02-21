import os
import sys
sys.path.append('../Libraries/trade')

from technical import *
from backtest import Optimize, TradeBotSim, GeneticCode


def indicators(data: dict, param: dict):
    atr_window = param['atr_window']
    atr_multiply = param['atr_multiply']
    peak_hold_term = param['peak_hold_term']
    ATR_TRAIL(data, atr_window, atr_multiply, peak_hold_term)
    
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
    
class OptimizeTrailATR(Optimize):
    def code_to_technical_param(self, code):
        atr_window = code[0]
        atr_multiply = code[1]
        peak_hold_term = code[2]
        param = {'atr_window': atr_window, 'atr_multiply': atr_multiply, 'peak_hold_term': peak_hold_term}
        return param, ['atr_window', 'atr_multiply', 'peak_hold_term']
        
    def code_to_trade_param(self, code):
        if len(code) != 1:
            raise Exception('trade_param length error')
        sl = code[0]
        target_profit = 0
        trailing_stop = 0
        param =  {'sl': sl, 'target_profit': target_profit, 'trailing_stop': trailing_stop, 'volume': 0.1, 'position_max': 5, 'timelimit': 0}
        return param, ['sl']
    
    def create_gene_space(self):
        symbol = self.symbol
        gene_space = None
        if symbol == 'NIKKEI' or symbol == 'DOW':
            r =  [GeneticCode.GeneFloat, 50, 500, 50]    
        elif symbol == 'NSDQ': #16000
            r = [GeneticCode.GeneFloat, 20, 200, 20]
        elif symbol == 'HK50':    
            r = [GeneticCode.GeneFloat, 50, 400, 50]
        elif symbol == 'USDJPY' or symbol == 'EURJPY':
            r = [GeneticCode.GeneFloat, 0.05, 0.5, 0.05]
        elif symbol == 'EURUSD': #1.0
            r = [GeneticCode.GeneFloat, 0.0005, 0.005, 0.0005]
        elif symbol == 'GBPJPY':
            r = [GeneticCode.GeneFloat, 0.05, 0.5, 0.05]
        elif symbol == 'AUDJPY': # 100
            r = [GeneticCode.GeneFloat, 0.025, 0.5, 0.025]
        elif symbol == 'XAUUSD': #2000
            r = [GeneticCode.GeneFloat, 0.5, 5.0, 0.5] 
        elif symbol == 'CL': # 70
            r = [GeneticCode.GeneFloat, 0.02, 0.2, 0.02] 
        else:
            raise Exception('Bad symbol')

        d = [0.0] + list(np.arange(r[1], r[2], r[3]))
        sl = r

        technical_space = [
                        [GeneticCode.GeneInt,   5, 1000, 5],     # atr_window
                        [GeneticCode.GeneFloat, 0.2, 4.0, 0.2],    # atr_multiply
                        [GeneticCode.GeneInt,   5, 100, 5]     # peak_hol_term
        ]

        trade_space = [ 
                        sl,                                       # stoploss
                        ] 
        return technical_space, trade_space

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
        optimize = OptimizeTrailATR('TrailATR', symbol, timeframe, indicators, TradeBotSimTrailATR)
        if optimize.load_data(2020, 1, 2024, 2):
            optimize.run(number)
        else:
            print(symbol + ": No data")
               
if __name__ == '__main__':
    main()