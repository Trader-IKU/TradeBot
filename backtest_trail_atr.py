import os
import sys
sys.path.append('../Libraries/trade')

from backtest import Optimize, indicators, TradeBotSim


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
        optimize = Optimize(symbol, timeframe, indicators, TradeBotSim)
        if optimize.load_data(2020, 1, 2024, 2):
            optimize.run(number)
        else:
            print(symbol + ": No data")
               
if __name__ == '__main__':
    main()