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
import sched

from candle_chart import CandleChart, makeFig, gridFig
from data_buffer import df2dic, DataBuffer, utc2jst
from time_utils import TimeUtils
from utils import Utils
from technical import Signal, Indicators, UP, DOWN, DOWN_TO_UP, UP_TO_DOWN, SL_TP_TYPE_NONE, SL_TP_TYPE_FIX, SL_TP_TYPE_AUTO

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

# -----

scheduler = sched.scheduler()

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
        self.positions_info = {}
        df = self.mt5.get_rates(self.timeframe, INITIAL_DATA_LENGTH)
        if len(df) < INITIAL_DATA_LENGTH:
            raise Exception('Error in initial data loading')
        if is_market_open(self.mt5, self.server_timezone):
            # last data is invalid
            df = df.iloc[:-1, :]
            buffer = DataBuffer(self.symbol, self.timeframe, df, self.technical_params, self.delta_hour_from_gmt)
            self.buffer = buffer
            save(buffer.data, './debug/initial_' + self.symbol + '_' + datetime.now().strftime('%Y-%m-%d_%H_%M_%S') + '.xlsx')
            return True            
        else:
            buffer = DataBuffer(self.symbol, self.timeframe, df, self.technical_params, self.delta_hour_from_gmt)
            self.buffer = buffer
            return False
         
    def run_simulate(self, df: pd.DataFrame):
        self.positions_info = {}
        self.count = INITIAL_DATA_LENGTH
        buffer = DataBuffer(self.symbol, self.timeframe, df, self.technical_params,  self.delta_hour_from_gmt)
        self.buffer = buffer
        save(buffer.data, './debug/initial_data_' + datetime.now().strftime('%Y-%m-%d_%H_%M_%S') + '.xlsx') 
        print('Data loaded', self.symbol, self.timeframe)   
        return True
    
    def close_all_postion(self):
        for key, info in self.positions_info.items():
            ret, _ = self.mt5.close_by_position_info(info)
            if ret:
                self.positions_info.pop(info.ticket)
                self.printing('<決済途転> Success', self.symbol, info.desc())
            else:
                self.printing('<決済途転> Fail', self.symbol, info.desc())           
    
    def update(self):
        self.check_positions()
        df = self.mt5.get_rates(self.timeframe, 2)
        df = df.iloc[:-1, :]
        n = self.buffer.update(df)
        if n > 0:
            current_time = self.buffer.last_time()
            current_index = self.buffer.last_index()
            save(self.buffer.data, './debug/update_' + self.symbol + '_' + datetime.now().strftime('%Y-%m-%d_%H_%M_%S') + '.xlsx')
            self.check_timeup(current_index)
            if self.trade_params['tp_type'] == SL_TP_TYPE_NONE or self.trade_params['tp'] == 0:
                #ドテン
                sig = self.check_reversal(self.buffer.data)
                if sig is not None:
                    self.close_all_position()            
            sig = self.check_signal(self.buffer.data)
            if sig == Signal.LONG or sig == Signal.SHORT:
                self.update_positions()
                self.order(sig, current_time, current_index)
                if sig == Signal.LONG:
                    entry = 'Long'
                else:
                    entry = 'Short'
                self.printing('<Signal>',  self.symbol, entry)
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
    
    def printing(self, *args):
        utc = utcnow()
        jst = utc2localize(utc, JST)
        tserver = utc2localize(utc, self.server_timezone)  
        s = jst.strftime('%Y-%m-%d_%H:%M:%S') + ' ('
        s += tserver.strftime('%Y-%m-%d_%H:%M:%S') +')'
        for arg in args:
            s += ' '
            s += str(arg) 
        print(s)
    
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
            self.printing('<自動決済> ', self.symbol, 'ticket:', ticket)
                                
    def check_timeup(self, current_index: int):
        positions = self.mt5.get_positions()
        timelimit = int(self.trade_params['timelimit'])
        for position in positions:
            if position.ticket in self.positions_info.keys():
                info = self.positions_info[position.ticket]
                if (current_index - info.index_open) >= timelimit:
                    ret, info = self.mt5.close_by_position_info(info)
                    if ret:
                        self.positions_info.pop(position.ticket)
                        self.printing('<決済タイムアップ> Success', self.symbol, info.desc())
                    else:
                        self.printing('<決済タイムアップ> Fail', self.symbol, info.desc())                                
                                
    def update_positions(self):
        positions = self.mt5.get_positions()
        for position in positions:
            if position.ticket in self.positions_info.keys():
                info = self.positions_info[position.ticket]
                if info.should_fire():
                    ret, info = self.mt5.close_by_position_info(info)
                    if ret:
                        self.positions_info.pop(position.ticket)
                        self.printing('<決済> Success...', self.symbol, info.desc())
                    else:
                        self.printing('<決済> Fail...', self.symbol, info.desc())
                        
    def calc_stoploss(self, signal, data:dict, window:int):
        if signal == Signal.LONG:
            d = data[Columns.LOW][-window:]
            return min(d)
        elif signal == Signal.SHORT:
            d = data[Columns.HIGH][-window:]
            return max(d)
        else:
            raise Exception('Bad signal')
                                
    def order(self, signal, index: int, time: datetime):
        volume = self.trade_params['volume']
        logging.info('request_order:' + str(signal) + '.' + str(time) + '.' + str(volume))
        positions = self.mt5.get_positions()
        if len(positions) >= int(self.trade_params['position_max']):
            self.printing('<エントリ> リクエストキャンセル ', self.symbol, 'ポジション数', len(positions))
            return
        sl_type = self.trade_params['sl_type']
        sl = self.trade_params['sl']
        tp_type = self.trade_params['tp_type']
        tp = self.trade_params['tp']
        if sl_type == SL_TP_TYPE_NONE:
            stoploss = 0
        elif sl_type == SL_TP_TYPE_FIX:
            stoploss = sl
        elif sl_type == SL_TP_TYPE_AUTO:
            stoploss = self.calc_stoploss(signal, self.buffer.data, 5)
        if tp_type == SL_TP_TYPE_NONE:
            takeprofit = 0
        elif tp_type == SL_TP_TYPE_FIX:
            takeprofit = tp
        ret, position_info = self.mt5.entry(signal, index, time, volume, stoploss=stoploss, takeprofit=takeprofit)
        position_info.entry_index = index
        position_info.entry_time = time
        if ret:
            position_info.timeup_count(self.trade_params['timelimit'])
            self.positions_info[position_info.ticket] = position_info
            self.printing('<発注> Success', self.symbol)

    def check_signal(self, data: dict):
        inverse = self.trade_params['inverse']
        trend = data[Indicators.SUPERTREND]
        entry_hold = self.trade_params['entry_hold']
        long_pattern = [DOWN, UP]
        for _ in range(entry_hold):
            long_pattern.append(UP)
        short_pattern = [UP, DOWN]
        for _ in range(entry_hold):
            short_pattern.append(DOWN)            
        d = trend[entry_hold - 2:]
        sig = None
        if d == long_pattern:
            if inverse:
                sig = Signal.SHORT
            else:
                sig = Signal.LONG
        if d == short_pattern:
            if inverse:
                sig = Signal.SHORT
            else:
                sig = Signal.Long
        return sig
    
    def check_reversal(self, data: dict):
        trend = data[Indicators.SUPERTREND]
        d = trend[-2:]
        if d == [DOWN, UP]:
            return DOWN_TO_UP    
        if d == [UP, DOWN]:
            return UP_TO_DOWN
        return None

    
def create_nikkei_bot():
    symbol = 'NIKKEI'
    timeframe = 'M5'
    technical = {'ATR':{'window': 40, 'multiply': 3.0}}
    trade = {'sl_type': SL_TP_TYPE_FIX, 'sl':150, 'tp_type': SL_TP_TYPE_NONE, 'tp': 0, 'entry_hold':1, 'inverse': 0,  'volume': 0.1, 'position_max': 1, 'timelimit': 40}
    bot = TradeBot(symbol, timeframe, 1, technical, trade)    
    return bot

def create_usdjpy_bot():
    symbol = 'USDJPY'
    timeframe = 'M5'
    technical = {'ATR':{'window': 60, 'multiply': 0.5}}
    trade =  {'sl_type': SL_TP_TYPE_FIX, 'sl':0.3, 'tp_type': SL_TP_TYPE_NONE, 'tp': 0, 'entry_hold':1, 'inverse': 0,  'volume': 0.1, 'position_max': 1, 'timelimit': 40}
    bot = TradeBot(symbol, timeframe, 1, technical, trade)    
    return bot
     
def test():
    Mt5Trade.connect()
    bot1 = create_nikkei_bot()
    bot1.set_sever_time(3, 2, 11, 1, 3.0)
    bot1.run()
    bot2 = create_usdjpy_bot()
    bot2.set_sever_time(3, 2, 11, 1, 3.0)
    bot2.run()
    while True:
        scheduler.enter(10, 1, bot1.update)
        #scheduler.run()
        scheduler.enter(10, 2, bot2.update)
        scheduler.run()
    
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