import os
import sys
sys.path.append('../Libraries/trade')

import time
import numpy as np
import pandas as pd
import pytz
from datetime import datetime, timedelta
from mt5_trade import Mt5Trade, Columns

from candle_chart import CandleChart, makeFig, gridFig
from data_buffer import df2dic, DataBuffer
from time_utils import TimeUtils
from utils import Utils


import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('./log/trade.log')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

INITIAL_DATA_LENGTH = 1000

class TradeBot:
    def __init__(self, symbol:str, timeframe:str, interval_seconds:int, technical_params: dict, trade_params:dict):
        self.symbol = symbol
        self.timeframe = timeframe
        self.invterval_seconds = interval_seconds
        self.technical_params = technical_params
        self.trade_params = trade_params
        mt5 = Mt5Trade(self.symbol)
        self.mt5 = mt5
        
    def run(self):
        
        df = self.mt5.get_rates(self.timeframe, INITIAL_DATA_LENGTH)
        if len(df) < INITIAL_DATA_LENGTH:
            raise Exception('Error in initial data loading')
        if self.is_market_open():
            # last data is invalid
            df = df.iloc[:-1, :]
            buffer = DataBuffer(self.symbol, self.timeframe, df, self.technical_params)
            self.buffer = buffer            
        else:
            buffer = DataBuffer(self.symbol, self.timeframe, df, self.technical_params)
            self.buffer = buffer
            self.wait_market_open()
        print('Data loaded', self.symbol, self.timeframe)    
    
    def is_market_open(self):
        t = datetime.utcnow() - timedelta(seconds=5)
        df = self.mt5.get_ticks_from(t, length=100)
        return (len(df) > 0)
            
    def wait_market_open(self):
        while self.is_market_open() == False:
            time.sleep(5)
    
        

def test():
    symbol = 'NIKKEI'
    timeframe = 'M30'
    technical = {'MA': {'window': 60}, 'ATR':{'window': 9, 'multiply': 2.0}}
    p = {'losscuts':[], 'entry':Columns.OPEN, 'exit':Columns.OPEN}
    bot = TradeBot(symbol, timeframe, 1, technical, p)
    bot.run()
    
if __name__ == '__main__':

    test()