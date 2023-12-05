import os
import sys
sys.path.append('../Libraries/trade')

import time
import threading
import numpy as np
import pandas as pd
import pytz
from datetime import datetime, timedelta
from mt5_trade import Mt5Trade, Columns

from candle_chart import CandleChart, makeFig, gridFig
from data_buffer import df2dic, DataBuffer
from time_utils import TimeUtils
from utils import Utils
from technical import Signal, Indicators, UP, DOWN


import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('./log/trade.log')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

INITIAL_DATA_LENGTH = 1000



class Scheduler:
    def __init__(self, interval_sec: float):
        self.interval_sec = interval_sec
    def run(self, target_function, wait=True):
        t0 = time.time()
        while True:
            thread = threading.Thread(target=target_function)
            thread.start()
            if wait:
                thread.join()
                sleep_time = (t0 - time.time()) % self.interval_sec
                if sleep_time > 0:
                    time.sleep(sleep_time)

scheduler = Scheduler(1.0)

def is_market_open(mt5):
    t = datetime.utcnow() - timedelta(seconds=5)
    df = mt5.get_ticks_from(t, length=100)
    return (len(df) > 0)
        
def wait_market_open(mt5):
    if is_market_open(mt5) == False:
        time.sleep(5)

class TradeBot:
    def __init__(self, symbol:str, timeframe:str, interval_seconds:int, technical_params: dict, trade_params:dict, simulate=False):
        self.symbol = symbol
        self.timeframe = timeframe
        self.invterval_seconds = interval_seconds
        self.technical_params = technical_params
        self.trade_params = trade_params
        if not simulate:
            mt5 = Mt5Trade(self.symbol)
            self.mt5 = mt5
        
    def run(self):
        df = self.mt5.get_rates(self.timeframe, INITIAL_DATA_LENGTH)
        if len(df) < INITIAL_DATA_LENGTH:
            raise Exception('Error in initial data loading')
        if is_market_open(self.mt5):
            # last data is invalid
            df = df.iloc[:-1, :]
            buffer = DataBuffer(self.symbol, self.timeframe, df, self.technical_params)
            self.buffer = buffer
            return True            
        else:
            buffer = DataBuffer(self.symbol, self.timeframe, df, self.technical_params)
            self.buffer = buffer
            return False
        print('Data loaded', self.symbol, self.timeframe)    

    def run_simulate(self, df: pd.DataFrame):
        self.count = 500
        buffer = DataBuffer(self.symbol, self.timeframe, df, self.technical_params)
        self.buffer = buffer
        print('Data loaded', self.symbol, self.timeframe)   
    
    def update(self):
        df = self.mt5.get_rates(self.timeframe, 2)
        df = df.iloc[:-1, :]
        n = self.buffer.update(df)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'Update data size', n)
        return n
    
    def update_simulate(self):
        df = df_data.iloc[:self.count, :]
        n = self.buffer.update(df)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'Update data size', n)
        self.count += 1
        sig = self.check_reversal(self.buffer.data)
        if sig == Signal.LONG or sig == Signal.SHORT:
            open_price = df[Columns.OPEN].values[-1]
            self.order(sig, open_price)
        return n
    
    def order(self, signal, open_price):
        t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(t, signal, open_price)
        pass
    
    def check_reversal(self, data: dict):
        trend = data[Indicators.SUPERTREND]
        n = len(trend)
        i = n - 1 
        if trend[i - 1] == DOWN and trend[i] == UP:
            return Signal.LONG
        if trend[i - 1] == UP and trend[i] == DOWN:
            return Signal.SHORT
        return None
    
def test1():
    symbol = 'NIKKEI'
    timeframe = 'M30'
    technical = {'MA': {'window': 60}, 'ATR':{'window': 9, 'multiply': 2.0}}
    p = {'losscuts':[], 'entry':Columns.OPEN, 'exit':Columns.OPEN}
    bot = TradeBot(symbol, timeframe, 1, technical, p)
    r = bot.run()
    if r == False:
        wait_market_open(bot.mt5)
    bot.update()
    bot.update()
    bot.update()
    
def test2():
    global df_data
    path = '../MarketData/Axiory/NIKKEI/M30/NIKKEI_M30_2023_06.csv'
    df_data = pd.read_csv(path)
    df1 = df_data.iloc[:500, :]
    
    symbol = 'NIKKEI'
    timeframe = 'M30'
    technical = {'MA': {'window': 60}, 'ATR':{'window': 9, 'multiply': 2.0}}
    p = {'losscuts':[], 'entry':Columns.OPEN, 'exit':Columns.OPEN}
    bot = TradeBot(symbol, timeframe, 1, technical, p, simulate=True)
    bot.run_simulate(df1)
    scheduler.run(bot.update_simulate)
    
if __name__ == '__main__':
    test2()