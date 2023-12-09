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
from data_buffer import df2dic, DataBuffer, utc2jst
from time_utils import TimeUtils
from utils import Utils
from technical import Signal, Indicators, UP, DOWN

JST = pytz.timezone('Asia/Tokyo')

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
filename = 'trade_' + datetime.now(JST).strftime('%y%m%d_%H%M') + '.log'
handler = logging.FileHandler(os.path.join('./log', filename))
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


INITIAL_DATA_LENGTH = 1048


class Scheduler:
    def __init__(self, interval_sec: float):
        self.interval_sec = interval_sec
        self.loop = False
        
    def run(self, target_function, wait=True):
        t0 = time.time()
        self.loop = True
        while self.loop:
            thread = threading.Thread(target=target_function)
            thread.start()
            if wait:
                thread.join()
                sleep_time = (t0 - time.time()) % self.interval_sec
                if sleep_time > 0:
                    time.sleep(sleep_time)
        print('Loop stopped')
        
    def stop(self):
        self.loop = False

# -----

scheduler = Scheduler(10.0)

# -----
def is_market_open(mt5):
    t = datetime.utcnow() - timedelta(seconds=5)
    df = mt5.get_ticks_from(t, length=100)
    return (len(df) > 0)
        
def wait_market_open(mt5):
    if is_market_open(mt5) == False:
        time.sleep(5)


def save(data, path):
    d = data.copy()
    time = d[Columns.TIME] 
    d[Columns.TIME] = [str(t) for t in time]
    jst = d[Columns.JST]
    d[Columns.JST] = [str(t) for t in jst]
    df = pd.DataFrame(d)
    df.to_excel(path, index=False)
    
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
        
    def set_sever_time(self, begin_month, begin_sunday, end_month, end_sunday, delta_hour_from_gmt_in_summer):
        now = datetime.now(JST)
        self.delta_hour_from_gmt = TimeUtils.delta_hour_from_gmt(now, begin_month, begin_sunday, end_month, end_sunday, delta_hour_from_gmt_in_summer)
        print('SeverTime GMT+', self.delta_hour_from_gmt)
        
    def run(self):
        df = self.mt5.get_rates(self.timeframe, INITIAL_DATA_LENGTH)
        if len(df) < INITIAL_DATA_LENGTH:
            raise Exception('Error in initial data loading')
        if is_market_open(self.mt5):
            # last data is invalid
            #df = df.iloc[:-1, :]
            buffer = DataBuffer(self.symbol, self.timeframe, df, self.technical_params, self.delta_hour_from_gmt)
            self.buffer = buffer
            save(buffer.data, './debug/initial_data_' + datetime.now().strftime('%Y-%m-%d_%H_%M_%S') + '.xlsx')
            return True            
        else:
            buffer = DataBuffer(self.symbol, self.timeframe, df, self.technical_params, self.delta_hour_from_gmt)
            self.buffer = buffer
            return False
        print('Data loaded', self.symbol, self.timeframe)    

    def run_simulate(self, df: pd.DataFrame):
        self.count = 500
        buffer = DataBuffer(self.symbol, self.timeframe, df, self.technical_params,  self.delta_hour_from_gmt)
        self.buffer = buffer
        print('Data loaded', self.symbol, self.timeframe)   
    
    def update(self):
        df = self.mt5.get_rates(self.timeframe, 1)
        #df = df.iloc[:-1, :]
        n = self.buffer.update(df)
        if n > 0:
            save(self.buffer.data, './debug/update_data_' + datetime.now().strftime('%Y-%m-%d_%H_%M_%S') + '.xlsx')
            sig = self.check_reversal(self.buffer.data)
            if sig == Signal.LONG or sig == Signal.SHORT:
                open_price = df[Columns.OPEN].values[-1]
                #self.order(sig, open_price)
                utc = datetime.now()
                jst = utc2jst(utc)
                if sig == Signal.LONG:
                    entry = 'Long'
                else:
                    entry = 'Short'
                print(utc.strftime('%Y-%m-%d %H:%M:%S'), '(JST: ' + jst.strftime('%Y-%m-%d %H:%M:%S') + ')', entry, 'Price:', open_price)
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
        if np.isnan(trend[i-1]) or np.isnan(trend[i]):
            return None
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
    bot.set_sever_time(3, 2, 11, 1, 3.0)
    r = bot.run()
    if r == False:
        wait_market_open(bot.mt5)
    scheduler.run(bot.update)
    
    
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
    bot.set_sever_time(3, 2, 11, 1, 3.0)
    bot.run_simulate(df1)
    scheduler.run(bot.update_simulate)
    
if __name__ == '__main__':
    test1()