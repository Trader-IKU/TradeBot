import os
import sys
sys.path.append('../Libraries/trade')

import time
import threading
import numpy as np
import pandas as pd
from dateutil import tz
from datetime import datetime, timedelta, timezone
from mt5_trade import Mt5Trade, Columns

from candle_chart import CandleChart, makeFig, gridFig
from data_buffer import df2dic, DataBuffer, utc2jst
from time_utils import TimeUtils
from utils import Utils
from technical import Signal, Indicators, UP, DOWN

JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc')  

import logging
log_path = './log/trade_' + datetime.now().strftime('%y%m%d_%H%M') + '.log'
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %I:%M:%S %p"
)


INITIAL_DATA_LENGTH = 200


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
def utcnow():
    utc = datetime.utcnow()
    utc = utc.replace(tzinfo=UTC)
    return utc

def utc2localize(aware_utc_time, timezone):
    t = aware_utc_time.astimezone(timezone)
    return t

def is_market_open(mt5, timezone):
    now = utcnow()
    t = utc2localize(now, timezone)
    t -= timedelta(seconds=5)
    df = mt5.get_ticks_from(t, length=100)
    return (len(df) > 0)
        
def wait_market_open(mt5, timezone):
    while is_market_open(mt5, timezone) == False:
        time.sleep(5)

def save(data, path):
    d = data.copy()
    time = d[Columns.TIME] 
    d[Columns.TIME] = [str(t) for t in time]
    jst = d[Columns.JST]
    d[Columns.JST] = [str(t) for t in jst]
    df = pd.DataFrame(d)
    df.to_excel(path, index=False)
    
    
def printing(*args):
    s = datetime.now().strftime('%Y-%m-%d_%H:%M:%S') + ' '
    for arg in args:
        s += ' '
        s += str(arg) 
    print(s)
    
class OrderInfo:
    def __init__(self, signal, time_entry, volume, stoploss, takeprofit):
        self.signal = signal
        self.time_entry = time_entry
        self.volume = volume
        self.stoploss = stoploss
        self.takeprofit = takeprofit
        
class TradeBot:
    def __init__(self, symbol:str, timeframe:str, interval_seconds:int, technical_params: dict, trade_params:dict, simulate=False):
        self.symbol = symbol
        self.timeframe = timeframe
        self.invterval_seconds = interval_seconds
        self.technical_params = technical_params
        self.trade_params = trade_params
        if not simulate:
            mt5 = Mt5Trade(symbol)
            self.mt5 = mt5
        self.delta_hour_from_gmt = None
        self.server_timezone = None
        
    def set_sever_time(self, begin_month, begin_sunday, end_month, end_sunday, delta_hour_from_gmt_in_summer):
        now = datetime.now(JST)
        dt, tz = TimeUtils.delta_hour_from_gmt(now, begin_month, begin_sunday, end_month, end_sunday, delta_hour_from_gmt_in_summer)
        self.delta_hour_from_gmt  = dt
        self.server_timezone = tz
        print('SeverTime GMT+', dt, tz)
        
    def run(self):
        self.orders = []
        self.positions_info = {}
        df = self.mt5.get_rates(self.timeframe, INITIAL_DATA_LENGTH)
        if len(df) < INITIAL_DATA_LENGTH:
            raise Exception('Error in initial data loading')
        if is_market_open(self.mt5, self.server_timezone):
            # last data is invalid
            df = df.iloc[:-1, :]
            buffer = DataBuffer(self.symbol, self.timeframe, df, self.technical_params, self.delta_hour_from_gmt)
            self.buffer = buffer
            save(buffer.data, './debug/initial_data_' + datetime.now().strftime('%Y-%m-%d_%H_%M_%S') + '.xlsx')
            return True            
        else:
            buffer = DataBuffer(self.symbol, self.timeframe, df, self.technical_params, self.delta_hour_from_gmt)
            self.buffer = buffer
            return False
         

    def run_simulate(self, df: pd.DataFrame):
        self.orders = []
        self.positions_info = {}
        self.count = INITIAL_DATA_LENGTH
        buffer = DataBuffer(self.symbol, self.timeframe, df, self.technical_params,  self.delta_hour_from_gmt)
        self.buffer = buffer
        save(buffer.data, './debug/initial_data_' + datetime.now().strftime('%Y-%m-%d_%H_%M_%S') + '.xlsx') 
        print('Data loaded', self.symbol, self.timeframe)   
        return True
    
    def update(self):
        self.check_positions()
        df = self.mt5.get_rates(self.timeframe, 2)
        df = df.iloc[:-1, :]
        n = self.buffer.update(df)
        if n > 0:
            t_update = self.buffer.last_time()
            save(self.buffer.data, './debug/update_data_' + datetime.now().strftime('%Y-%m-%d_%H_%M_%S') + '.xlsx')
            sig = self.check_reversal(self.buffer.data)
            if sig == Signal.LONG or sig == Signal.SHORT:
                self.update_positions(t_update)
                self.request_order(sig, t_update, self.trade_params['volume'], self.trade_params['sl'], self.trade_params['tp'])
                if sig == Signal.LONG:
                    entry = 'Long'
                else:
                    entry = 'Short'
                printing('<Reverse Signal>',  entry)
            self.order()
        return n
    
    def update_simulate(self):
        df = df_data.iloc[self.count, :]
        self.count += 1
        n = self.buffer.update(df)
        if n > 0:
            t_update = self.buffer.last_time()
            self.update_positions(t_update)
            save(self.buffer.data, './debug/update_data_' + datetime.now().strftime('%Y-%m-%d_%H_%M_%S') + '.xlsx')
            sig = self.check_reversal(self.buffer.data)
            if sig == Signal.LONG or sig == Signal.SHORT:
                self.request_order(sig, t_update, self.trade_params['volume'], self.trade_params['sl'], self.trade_params['tp'])
                jst = datetime.now()
                if sig == Signal.LONG:
                    entry = 'Long'
                else:
                    entry = 'Short'
                print(jst.strftime('%Y-%m-%d %H:%M:%S') , entry)
            self.order()
        return n
    
    def calc_time(self, time: datetime, timeframe: str, horizon: int):
        num = int(timeframe[1:])
        if timeframe[0].upper() == 'M':
            dt = timedelta(minutes=num * horizon)
        elif timeframe[0].upper() == 'H':
            dt = timedelta(hours=num * horizon)
        return (time + dt)
    
    def check_positions(self):
        positions = self.mt5.get_positions()
        remove = []
        for ticket, info in self.positions_info.items():
            found = False
            for position in positions:
                if position.ticket == ticket:
                    found = True
                    break    
            if found == False: 
                remove.append(ticket)    
        for ticket in remove:
            self.positions_info.pop(ticket)
            printing('<自動決済> Position is closed automatic: ', ticket)
                                
    def update_positions(self, time: datetime):
        #time_exit = self.calc_time(time, self.timeframe, self.trade_params['exit_horizon'])
        positions = self.mt5.get_positions()
        for position in positions:
            if position.ticket in self.positions_info.keys():
                info = self.positions_info[position.ticket]
                if info.should_fire():
                    ret, info = self.mt5.close_by_position_info(info)
                    if ret:
                        self.positions_info.pop(position.ticket)
                        printing('<決済> Close Success...', info.desc())
                    else:
                        printing('<決済> Close Fail...', info.desc())
                        
    def request_order(self, signal, time: datetime, volume, stoploss, takeprofit):
        logging.info('request_order:' + str(signal) + '.' + str(time) + '.' + str(volume))
        time_entry = self.calc_time(time, self.timeframe, self.trade_params['entry_horizon'])
        order = OrderInfo(signal, time_entry, volume, stoploss, takeprofit)
        self.orders.append(order)
                                                
    def order(self):
        remains = []
        for i, order in enumerate(self.orders):
            tlast = self.buffer.last_time()
            if order.time_entry <= tlast:
                ret, position_info = self.mt5.entry(order.signal, order.volume, stoploss=order.stoploss, takeprofit=order.takeprofit)
                if ret:
                    position_info.fire_count(self.trade_params['exit_horizon'])
                    self.positions_info[position_info.ticket] = position_info
                    printing('<発注> Entry Success', order)
                else:
                    printing('<発注> Entry Fail', order)
            else:
                remains.append(i)
        new_orders = [self.orders[i] for i in remains]
        self.orders = new_orders

    def check_reversal(self, data: dict):
        inverse = self.trade_params['inverse']
        trend = data[Indicators.SUPERTREND]
        n = len(trend)
        i = n - 1 
        if np.isnan(trend[i-1]) or np.isnan(trend[i]):
            return None
        if trend[i - 1] == DOWN and trend[i] == UP:
            if inverse > 0:
                return Signal.SHORT
            else:
                return Signal.LONG
        if trend[i - 1] == UP and trend[i] == DOWN:
            if inverse:
                return Signal.LONG
            else:
                return Signal.SHORT
        return None
    
    
def nikkei():
    symbol = 'NIKKEI'
    timeframe = 'M5'
    technical = {'ATR':{'window': 10, 'multiply': 1.0}}
    p = {'sl':300, 'tp': 120, 'entry_horizon':0, 'exit_horizon':0, 'inverse': 1,  'volume': 0.1}
    return symbol, timeframe, technical, p

def usdjpy():
    symbol = 'USDJPY'
    timeframe = 'M5'
    technical = {'ATR':{'window': 60, 'multiply': 0.5}}
    p = {'sl':0.3, 'tp': 0, 'entry_horizon':2, 'exit_horizon':1, 'inverse': 1,  'volume': 0.1}
    return symbol, timeframe, technical, p
     
def test():
    symbol, timeframe, technical_param, trade_param = nikkei() #usdjpy()
    bot = TradeBot(symbol, timeframe, 1, technical_param, trade_param)
    Mt5Trade.connect()
    bot.set_sever_time(3, 2, 11, 1, 3.0)
    r = bot.run()
    if r == False:
        wait_market_open(bot.mt5, bot.server_timezone)
    scheduler.run(bot.update)
    
def test_simulate():
    global df_data
    path = '../MarketData/Axiory/NIKKEI/M30/NIKKEI_M30_2023_06.csv'
    df_data = pd.read_csv(path)
    df1 = df_data.iloc[:INITIAL_DATA_LENGTH, :]
    
    symbol = 'NIKKEI'
    timeframe = 'M30'
    technical = {'ATR':{'window': 9, 'multiply': 2.0}}
    p = {'sl':100, 'tp': 0, 'entry_horizon':0, 'exit_horizon':0, 'inverse': 1,  'volume': 0.2}
    bot = TradeBot(symbol, timeframe, 1, technical, p, simulate=True)
    bot.set_sever_time(3, 2, 11, 1, 3.0)
    bot.run_simulate(df1)
    scheduler.run(bot.update_simulate)
    
if __name__ == '__main__':
    test()