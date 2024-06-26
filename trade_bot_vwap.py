import os
import shutil
import sys
sys.path.append('../Libraries/trade')

import time
import threading
import numpy as np
import pandas as pd
from dateutil import tz
from datetime import datetime, timedelta, timezone
from mt5_trade import Mt5Trade, Columns, PositionInfo
import sched

from candle_chart import CandleChart, makeFig, gridFig
from data_buffer import df2dic, DataBuffer, utc2jst
from time_utils import TimeUtils, TimeFilter
from utils import Utils
from technical import *

JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc')  

import logging


def create_dir(path):     
    try:
        shutil.rmtree(path)
    except:
        pass
    os.makedirs(path, exist_ok=True)
    return path

log_dir = create_dir('./log')
log_path = os.path.join(log_dir, 'trade_' + datetime.now().strftime('%y%m%d_%H%M') + '.log')
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %I:%M:%S %p"
)

create_dir('./debug')

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
    
class TradeManager:
    def __init__(self, symbol, timeframe):
        self.symbol = symbol
        self.timeframe = timeframe
        self.positions = {}
        self.positions_closed = {}

    def add_position(self, position: PositionInfo):
        self.positions[position.ticket] = position
       
    def move_to_closed(self, ticket):
        if ticket in self.positions.keys():
            pos = self.positions.pop(ticket)
            self.positions_closed[ticket] = pos
        else:
            print('move_to_closed, No tickt')
        
    def remove_positions(self, tickets):
        for ticket in tickets:
            self.move_to_closed(ticket)
            
    def open_positions(self):
        return self.positions
    
    def untrail_positions(self):
        positions = []
        for ticket, position in self.positions.items():
            if position.profit_max is None:
                positions.append(position)
        return positions
    
    def remove_position_auto(self, mt5_positions):
        remove_tickets = []
        for ticket, info in self.positions.items():
            found = False
            for position in mt5_positions:
                if position.ticket == ticket:
                    found = True
                    break    
            if found == False:
                remove_tickets.append(ticket)
        if len(remove_tickets):
            self.remove_positions(remove_tickets)    
            print('<Closed by Meta Trader Stoploss or Takeprofit> ', self.symbol, 'tickets:', remove_tickets)
            
class TradeBot:
    def __init__(self, symbol:str, timeframe:str, interval_seconds:int, technical_param: dict, trade_param:dict, timefilter, simulate=False):
        self.symbol = symbol
        self.timeframe = timeframe
        self.invterval_seconds = interval_seconds
        self.technical_param = technical_param
        self.trade_param = trade_param
        self.timefilter = timefilter
        if not simulate:
            mt5 = Mt5Trade(symbol)
            self.mt5 = mt5
        self.delta_hour_from_gmt = None
        self.server_timezone = None
        
    def debug_print(self, *args):
        utc = utcnow()
        jst = utc2localize(utc, JST)
        t_server = utc2localize(utc, self.server_timezone)  
        s = 'JST*' + jst.strftime('%Y-%m-%d_%H:%M:%S') + ' (ServerTime:' +  t_server.strftime('%Y-%m-%d_%H:%M:%S') +')'
        for arg in args:
            s += ' '
            s += str(arg) 
        print(s)    
        
    def calc_indicators(self, data: dict, param: dict):
        vwap_begin_hour = param['vwap_begin_hour']
        VWAP(data, param['vwap_multiply'], begin_hour=vwap_begin_hour)
        #ATR(data, 15, 100)
        BB(data, param['bb_window'], param['bb_ma_window'], param['bb_multiply'])
        
    def set_sever_time(self, begin_month, begin_sunday, end_month, end_sunday, delta_hour_from_gmt_in_summer):
        now = datetime.now(JST)
        dt, tz = TimeUtils.delta_hour_from_gmt(now, begin_month, begin_sunday, end_month, end_sunday, delta_hour_from_gmt_in_summer)
        self.delta_hour_from_gmt  = dt
        self.server_timezone = tz
        print('SeverTime GMT+', dt, tz)
        
    def run(self):
        self.trade_manager = TradeManager(self.symbol, self.timeframe)
        df = self.mt5.get_rates(self.timeframe, INITIAL_DATA_LENGTH)
        if len(df) < INITIAL_DATA_LENGTH:
            raise Exception('Error in initial data loading')
        if is_market_open(self.mt5, self.server_timezone):
            # last data is invalid
            df = df.iloc[:-1, :]
            buffer = DataBuffer(self.calc_indicators, self.symbol, self.timeframe, df, self.technical_param, self.delta_hour_from_gmt)
            self.buffer = buffer
            save(buffer.data, './debug/initial_' + self.symbol + '_' + datetime.now().strftime('%Y-%m-%d_%H_%M_%S') + '.xlsx')
            return True            
        else:
            print('<マーケットクローズ>')
            buffer = DataBuffer(self.calc_indicators, self.symbol, self.timeframe, df, self.technical_param, self.delta_hour_from_gmt)
            self.buffer = buffer
            return False
    
    def update(self):
        self.remove_closed_positions()
        self.trailing()
        df = self.mt5.get_rates(self.timeframe, 2)
        df = df.iloc[:-1, :]
        n = self.buffer.update(df)
        if n > 0:
            current_time = self.buffer.last_time()
            current_index = self.buffer.last_index()
            save(self.buffer.data, './debug/update_' + self.symbol + '_' + datetime.now().strftime('%Y-%m-%d_%H_%M_%S') + '.xlsx')
            #self.check_timeup(current_index)
            if self.timefilter.on(current_time) == False:
                positions = self.trade_manager.open_positions()
                if len(positions) > 0:
                    self.debug_print('<Close all at day end>', self.symbol,)       
                    self.close_positions(positions)
                return n
            sig_exit = self.detect_exit(self.buffer.data)
            if sig_exit == Signal.LONG or sig_exit == Signal.SHORT:
                self.exit_positons(sig_exit)
            sig_entry = self.detect_entry(self.buffer.data)
            if sig_entry == Signal.LONG or sig_entry == Signal.SHORT:
                self.debug_print('<Signal> ', sig_entry)
                self.entry(self.buffer.data, sig_entry, current_index, current_time)
        return n
    
    def detect_entry(self, data: dict):
        vwap_cross = data[Indicators.VWAP_CROSS]
        bb_cross = data[Indicators.BB_CROSS]
        if vwap_cross[-1] == UP:
            return Signal.LONG  
        elif vwap_cross[-1] == DOWN:
            return Signal.SHORT               
        return None
    
    def detect_exit(self, data: dict):
        vwap_cross = data[Indicators.VWAP_CROSS]
        bb_cross = data[Indicators.BB_CROSS]
        if self.trade_param['exit_type'] == 0:
            if vwap_cross[-1] == UP or bb_cross[-1] == UP:
                return Signal.LONG
            elif vwap_cross[-1] == DOWN or bb_cross[-1] == DOWN:
                return Signal.SHORT  
        else:
            if vwap_cross[-1] == UP:
                return Signal.LONG  
            elif vwap_cross[-1] == DOWN:
                return Signal.SHORT               
        return None
    
    def exit_positons(self, signal):
        remove_tickets = []
        for ticket, info in self.trade_manager.positions.items():
            if info.signal == signal:
                continue
            ret, info = self.mt5.close_by_position_info(info)
            if ret:
                remove_tickets.append(info.ticket)
                self.debug_print('<Closed by exit signal> Success', self.symbol, info.desc())   
        for ticket in remove_tickets:
            self.trade_manager.move_to_closed(ticket)    
        
    def mt5_position_num(self):
        positions = self.mt5.get_positions()
        count = 0
        for position in positions:
            if position.symbol == self.symbol:
                count += 1
        return count
        
    def entry(self, data, signal, index, time):
        volume = self.trade_param['volume']
        sl = self.trade_param['sl']
        target_profit = self.trade_param['target']
        trailing_stop = self.trade_param['trail_stop']          
        timelimit = self.trade_param['timelimit']                       
        position_max = int(self.trade_param['position_max'])
        num =  self.mt5_position_num()
        if num >= position_max:
            self.debug_print('<Entry> Request Canceled ', self.symbol, index, time,  'Position num', num)
            return
        if sl == 0:
            atr = data[Indicators.ATR]
            sl = atr[index] * 2.0
        ret, position_info = self.mt5.entry(signal, index, time, volume, stoploss=sl, takeprofit=None)
        position_info.target_profit = target_profit
        if ret:
            self.trade_manager.add_position(position_info)
            self.debug_print('<Entry> signal', position_info.signal, position_info.symbol, position_info.entry_index, position_info.entry_time)

    def remove_closed_positions(self):
        positions = self.mt5.get_positions()
        self.trade_manager.remove_position_auto(positions)
        
    def trailing(self):
        trailing_stop = self.trade_param['trail_stop'] 
        target_profit = self.trade_param['target']
        if trailing_stop == 0 or target_profit == 0:
            return
        remove_tickets = []
        for ticket, info in self.trade_manager.positions.items():
            price = self.mt5.current_price(info.signal())
            triggered, profit, profit_max = info.update_profit(price)
            if triggered:
                self.debug_print('<Trailing fired> profit', profit_max)
            if profit_max is None:
                continue
            if (profit_max - profit) > trailing_stop:
                ret, info = self.mt5.close_by_position_info(info)
                if ret:
                    remove_tickets.append(info.ticket)
                    self.debug_print('<Closed trailing stop> Success', self.symbol, info.desc())
                else:
                    self.debug_print('<Closed trailin stop> Fail', self.symbol, info.desc())    
        for ticket in remove_tickets:
            self.trade_manager.move_to_closed(ticket)
                
    def check_timeup(self, current_index: int):
        positions = self.mt5.get_positions()
        timelimit = int(self.trade_param['timelimit'])
        remove_tickets = []
        for position in positions:
            if position.ticket in self.positions.keys():
                info = self.positions[position.ticket]
                if (current_index - info.entry_index) >= timelimit:
                    ret, info = self.mt5.close_by_position_info(info)
                    if ret:
                        remove_tickets.append(position.ticket)
                        self.debug_print('<Closed Timeup> Success', self.symbol, info.desc())
                    else:
                        self.debug_print('<Closed Timeup> Fail', self.symbol, info.desc())                                      
        self.trade_manager.remove_positions(remove_tickets)
       
    def close_positions(self, positions):   
        removed_tickets = []
        for position in positions:
            ret, _ = self.mt5.close_by_position_info(position)
            if ret:
                removed_tickets.append(position.ticket)
                self.debug_print('<Closed Doten> Success', self.symbol, position.desc())
            else:
                self.debug_print('<Closed Doten> Fail', self.symbol, position.desc())           
        self.trade_manager.remove_positions(removed_tickets)

def create_nikkei_bot():
    symbol = 'NIKKEI'
    timeframe = 'M5'
    technical = {'atr_window': 40, 'atr_multiply': 2.0}
    trade = {'sl': 100, 'target_profit': 100, 'trail_stop': 50, 'volume': 0.1, 'position_max': 5, 'timelimit': 40}
    bot = TradeBot(symbol, timeframe, 1, technical, trade)    
    return bot

def create_bot():
    symbol = 'NIKKEI'
    timeframe = 'M1'
    technical_param = {'bb_window':30, 'bb_ma_window':80, 'bb_multiply': 1.8, 'vwap_multiply': 3.8, 'vwap_begin_hour': 8}
    trade_param = {'sl': 150, 'target': 150, 'trail_stop': 120, 'exit_type': 0, 'volume': 0.1, 'position_max': 5, 'timelimit': 1}
    timefilter = TimeFilter(JST, 10, 0, 12)
    bot = TradeBot(symbol, timeframe, 1, technical_param, trade_param, timefilter)    
    return bot
     
def test():
    Mt5Trade.connect()
    bot1 = create_bot()
    bot1.set_sever_time(3, 2, 11, 1, 3.0)
    bot1.run()
    #bot2 = create_bot()
    #bot2.set_sever_time(3, 2, 11, 1, 3.0)
    #bot2.run()
    while True:
        scheduler.enter(10, 1, bot1.update)
        #scheduler.run()
        #scheduler.enter(10, 2, bot2.update)
        scheduler.run()

if __name__ == '__main__':
    test()