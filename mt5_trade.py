
import MetaTrader5 as mt5
import pandas as pd
import pytz
from datetime import datetime

class TimeFrame:
    TICK = 'TICK'
    M1 = 'M1'
    M5 = 'M5'
    M15 = 'M15'
    M30 = 'M30'
    H1 = 'H1'
    H4 = 'H4'
    D1 = 'D1'
    def __init__(self, timeframe_str: str):
        self.timeframe_str = timeframe_str
        timeframes = {self.M1: mt5.TIMEFRAME_M1, 
                      self.M5: mt5.TIMEFRAME_M5,
                      self.M15: mt5.TIMEFRAME_M15,
                      self.M30: mt5.TIMEFRAME_M30,
                      self.H1: mt5.TIMEFRAME_H1,
                      self.H4: mt5.TIMEFRAME_H4,
                      self.D1: mt5.TIMEFRAME_D1}
        self.timeframe = timeframes[timeframe_str]

class Trading:
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
        utc_aware = jst_aware.astimezone(pytz.timezone("Etc/UTC"))
        return utc_aware
    
    def utc2jst(self, utc_aware: datetime):
        jst_aware = utc_aware.astimezone(pytz.timezon('Asia/Tokyo'))
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
        
    def get_rates(self, timeframe: TimeFrame, utc_begin, utc_end):
        print(self.symbol, timeframe.timeframe)
        rates = mt5.copy_rates_range(self.symbol, timeframe.timeframe, utc_begin, utc_end)
        return self.parse_rates(rates)
    
    def df2dic(self, df: pd.DataFrame):
        dic = {}
        for column in df.columns:
            dic[column] = df[column].to_numpy()
        return dic
    
    def parse_rates(self, rates):
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
        