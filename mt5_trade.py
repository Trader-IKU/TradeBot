
import MetaTrader5 as mt5
import pandas as pd


class TimeFrame:
    M1 = 'M1'
    M5 = 'M5'
    M15 = 'M15'
    M30 = 'M30'
    H1 = 'H1'
    H4 = 'H4'
    D1 = 'D1'

class Trading:
    def __init__(self, symbol):
        self.symbol = symbol
        self.ticket = None

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
        
    def buy_limit(self, volume, price):
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
        
    def sell_limit(self, volume, price):
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
            "type": mt5.ORDER_TYPE_BUY if self.type == 1 else mt5.ORDER_TYPE_SELL,
            "price": tick.ask if self.type == 1 else tick.bid,
            "deviation": 20,
            "magic": 100,
            "comment": "python script close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        return result
    
    def get_tick(self, size):
        
        pass
    
    def get_rates(self, time_frame: TimeFrame):
        
        pass
        
        
        