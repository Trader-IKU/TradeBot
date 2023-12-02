
import MetaTrader5 as mt5
import pandas as pd
import pytz
from datetime import datetime, timedelta
import numpy as np
from dateutil import tz

JST = pytz.timezone('Asia/Tokyo')
UTC = pytz.timezone('utc')  


class Columns:
    TIME = 'time'
    JST = 'jst'
    OPEN = 'open'
    HIGH = 'high'
    LOW = 'low'
    CLOSE = 'close'    
    ASK = 'ask'
    BID = 'bid'


    
class TimeFrame:
    TICK = 'TICK'
    M1 = 'M1'
    M5 = 'M5'
    M15 = 'M15'
    M30 = 'M30'
    H1 = 'H1'
    H4 = 'H4'
    D1 = 'D1'
    
    timeframes = {  M1: mt5.TIMEFRAME_M1, 
                    M5: mt5.TIMEFRAME_M5,
                    M15: mt5.TIMEFRAME_M15,
                    M30: mt5.TIMEFRAME_M30,
                    H1: mt5.TIMEFRAME_H1,
                    H4: mt5.TIMEFRAME_H4,
                    D1: mt5.TIMEFRAME_D1}
            
    @staticmethod 
    def const(timeframe_str: str):
        return TimeFrame.timeframes[timeframe_str]
        
def npdatetime2datetime(npdatetime):
    timestamp = (npdatetime - np.datetime64('1970-01-01T00:00:00Z')) / np.timedelta64(1, 's')
    dt = datetime.utcfromtimestamp(timestamp)
    dt = UTC.localize(dt)
    return dt

def slice(df, ibegin, iend):
    new_df = df.iloc[ibegin: iend + 1, :]
    return new_df

def df2dic(df: pd.DataFrame):
    dic = {}
    for column in df.columns:
        dic[column] = df[column].to_numpy()
    return dic

def time_str_2_datetime(df, time_column, format='%Y-%m-%d %H:%M:%S'):
    time = df[time_column].to_numpy()
    new_time = [datetime.strptime(t, format) for t in time]
    df[time_column] = new_time

class Mt5Trade:
    def __init__(self, symbol):
        self.symbol = symbol
        self.ticket = None
        self.connect()
        
    def connect(self):
        if mt5.initialize():
            print('Connected to MT5 Version', mt5.version())
        else:
            print('initialize() failed, error code = ', mt5.last_error())
    
    def jst2utc(self, jst_naive: datetime):
        jst_aware = pytz.timezone("Asia/Tokyo").localize(datetime(2021, 4, 1, 11, 22, 33))
        utc_aware = jst_aware.astimezone(pytz.timezone(UTC))
        return utc_aware
    
    def utc2jst(self, utc_aware: datetime):
        jst_aware = utc_aware.astimezone(JST)
        return jst_aware

    def ticket(self):
        return self.ticket        
        
    def order_info(self, result):
        code = result.retcode
        if code == 10009:
            print("注文完了")
            self.ticket = result.ticket
            return True
        elif code == 10013:
            print("無効なリクエスト")
            return False
        elif code == 10018:
            print("マーケットが休止中")
            return False        
        
    def buy_limit(self, volume, price, is_long):
        self.is_long = is_long
        result = mt5.order_send({
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": self.symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY_LIMIT,
            "price": price,
            "deviation": 20,
            "magic": 100,
            "comment": "python market order",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        })
        return self.order_info(result)
        
    def sell_limit(self, volume, price, is_long):
        self.is_long = is_long
        result = mt5.order_send({
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": self.symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_SELL_LIMIT,
            "price": price,
            "deviation": 20,
            "magic": 100,
            "comment": "python market order",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        })
        return self.result_info(result)

    def get_positions(self):
        positions = mt5.positions_get(symbol=self.symbol)

    def close(self, volume):
        tick = mt5.symbol_info_tick(self.symbol)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": self.ticket,
            "symbol": self.symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY if self.is_long else mt5.ORDER_TYPE_SELL,
            "price": tick.ask if self.is_long else tick.bid,
            "deviation": 20,
            "magic": 100,
            "comment": "python script close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        return result
    
    def get_ticks_jst(self, jst_begin, jst_end):
        t_begin = self.jst2utc(jst_begin)
        t_end = self.jst2utc(jst_end)
        return self.get_ticks(t_begin, t_end)

    def get_ticks(self, utc_begin, utc_end):
        ticks = mt5.copy_ticks_range(self.symbol, utc_begin, utc_end, mt5.COPY_TICKS_ALL)
        return self.parse_ticks(ticks)    
        
    def parse_ticks(self, ticks):
        df = pd.DataFrame(ticks)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    
    def get_rates_jst(self, timeframe: TimeFrame, jst_begin, jst_end):
        t_begin = self.jst2utc(jst_begin)
        t_end = self.jst2utc(jst_end)
        return self.get_rates(timeframe, t_begin, t_end)
        
    def get_rates(self, timeframe: str, length: int):
        #print(self.symbol, timeframe)
        rates = mt5.copy_rates_from_pos(self.symbol,  TimeFrame.const(timeframe), 0, length)
        return self.parse_rates(rates)

    def parse_rates(self, rates):
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df[Columns.TIME], unit='s')
        return df
        
        
class Mt5TradeSim:
    def __init__(self, symbol: str, files: dict):
        self.symbol = symbol
        self.load_data(files)
                
    def adjust_msec(self, df, time_column, msec_column):
        new_time = []
        for t, tmsec in zip(df[time_column], df[msec_column]):
            msec = tmsec % 1000
            dt = t + timedelta(milliseconds= msec)
            new_time.append(dt)
        df[time_column] = new_time
                
    def load_data(self, files):
        dic = {}
        for timeframe, file in files.items():
            df = pd.read_csv(file)
            time_str_2_datetime(df, Columns.TIME)
            if timeframe == TimeFrame.TICK:
                self.adjust_msec(df, Columns.TIME, 'time_msc')
            dic[timeframe] = df
        self.dic = dic
    
    def search_in_time(self, df, time_column, utc_time_begin, utc_time_end):
        time = list(df[time_column].values)
        if utc_time_begin is None:
            ibegin = 0
        else:
            ibegin = None
        if utc_time_end is None:
            iend = len(time) - 1
        else:
            iend = None
        for i, t in enumerate(time):
            dt = npdatetime2datetime(t)
            if ibegin is None:
                if dt >= utc_time_begin:
                    ibegin = i
            if iend is None:
                if dt > utc_time_end:
                    iend = i - 1
            if ibegin is not None and iend is not None:
                break
        slilced = slice(df, ibegin, iend)
        return slilced

    def get_rates(self, timeframe: str, utc_begin, utc_end):
        print(self.symbol, timeframe)
        df = self.dic[timeframe]
        return self.search_in_time(df, Columns.TIME, utc_begin, utc_end)

    def get_ticks(self, utc_begin, utc_end):
        df = self.dic[TimeFrame.TICK]
        return self.search_in_time(df, Columns.TIME, utc_begin, utc_end)

