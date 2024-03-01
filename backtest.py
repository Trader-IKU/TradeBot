import os
import shutil
import sys
sys.path.append('../Libraries/trade')

import numpy as np
import pandas as pd
import random

import MetaTrader5 as mt5
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
from dateutil import tz
from mt5_trade import PositionInfo
from common import Columns, Signal, Indicators, UP, DOWN
from technical import MA, ATR, ADX, SUPERTREND, POLARITY, TREND_ADX_DI, moving_average
from time_utils import TimeUtils, TimeFilter
from utils import Utils
from candle_chart import *

JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc')  

class DataLoader:
    def server_time_str_2_datetime(self, server_time_str_list, server_timezone, format='%Y-%m-%d %H:%M:%S'):
        t_utc = []
        t_jst = []
        for time_str in server_time_str_list:
            t = datetime.strptime(time_str, format)
            t = t.replace(tzinfo=server_timezone)
            utc = t.astimezone(UTC)
            t_utc.append(utc)
            jst = t.astimezone(JST)        
            t_jst.append(jst)
        return t_utc, t_jst

    def data_filepath(self, symbol, timeframe, year, month):
        path = '../MarketData/Axiory/'
        dir_path = os.path.join(path, symbol, timeframe)
        name = symbol + '_' + timeframe + '_' + str(year) + '_' + str(month).zfill(2) + '.csv'
        filepath = os.path.join(dir_path, name)
        if os.path.isfile(filepath):
            return filepath 
        else:
            return None
        
    def load_data(self, symbol, timeframe, from_year, from_month, to_year, to_month):
        dfs = []
        year = from_year
        month = from_month
        while True:
            filepath = self.data_filepath(symbol, timeframe, year, month)
            if filepath is not None:
                df = pd.read_csv(filepath)
                dfs.append(df)
            if year == to_year and month == to_month:
                break
            month += 1
            if month > 12:
                year += 1
                month = 1
                
        if len(dfs) == 0:
            return 0
        df = pd.concat(dfs, ignore_index=True)
        n = len(df)
        dic = {}
        for column in df.columns:
            dic[column] = list(df[column].values)
        tzone = timezone(timedelta(hours=2))
        if timeframe.upper() == 'D1'or timeframe.upper() == 'W1':
            format='%Y-%m-%d'
        else:
            format='%Y-%m-%d %H:%M:%S'
        utc, jst = self.server_time_str_2_datetime(dic[Columns.TIME], tzone, format=format)
        dic[Columns.TIME] = utc
        dic[Columns.JST] = jst
        print(symbol, timeframe, 'Data size:', len(jst), jst[0], '-', jst[-1])
        self.size = n
        return n, dic
    
    def data(self):
        return self.dic
    
def indicators(data: dict, param: dict):
    atr_window = param['atr_window']
    atr_multiply = param['atr_multiply']
    #di_window = param['di_window']
    #adx_window = param['adx_window']
    #polarity_window = param['polarity_window']
    
    #MA(data, Columns.CLOSE, 5)
    ATR(data, atr_window, atr_window * 2)
    #ADX(data, di_window, adx_window, adx_window * 2)
    #POLARITY(data, polarity_window)
    #TREND_ADX_DI(data, 20)
    SUPERTREND(data, atr_multiply, column=Columns.MID)
        
class GeneticCode:
    DataType = int
    GeneInt: DataType = 1
    GeneFloat: DataType = 2
    GeneList: DataType = 3

    def __init__(self, gene_space):
        self.gene_space = gene_space
           
    def gen_number(self, gene_space):
        typ = gene_space[0]
        if typ == self.GeneList:
            lis = gene_space[1]
            n = len(lis)
            i = random.randint(0, n - 1)
            return lis[i]
        begin = gene_space[1]
        end = gene_space[2]
        step = gene_space[3]
        num = int((end - begin) / step) + 1
        i = random.randint(0, num - 1)
        out = begin + step * i
        if typ == self.GeneInt:
            return int(out)
        elif typ == self.GeneFloat:
            return float(out)
                
    def create_code(self):
        n = len(self.gene_space)
        code = []
        for i in range(n):
            space = self.gene_space[i]
            value = self.gen_number(space)
            code.append(value)
        return code        

class PositionInfoSim(PositionInfo):
            
    def losscut(self, index, time, hi, lo, cl):
        # losscut 
        profit0 = cl - self.entry_price
        profit1 = hi - self.entry_price
        profit2 = lo- self.entry_price
        if self.signal() == Signal.SHORT:
            profit0 *= -1
            profit1 *= -1
            profit2 *= -1
        profits = [profit0, profit1, profit2]
        if np.min(profits) < - self.sl:
            self.losscutted = True
            #print('<Losscut>',  'Signal', self.signal(), index, time,'Profit', np.min(profits))
            if self.signal() == Signal.SHORT:
                self.close(index, time, hi)
            else:
                self.close(index, time, lo)
                
    def trail(self, trailing_stop, index, time, cl):
        if trailing_stop == 0:
            return
        triggered, profit, profit_max = self.update_profit(cl)
        if profit_max is None:
            return
        if (profit_max - profit) > trailing_stop:
            self.close(index, time, cl)
            self.trailing_stopped = True
            #print('<Trailing Close>', 'Signal', self.signal(), index, time, 'price', cl, 'profit', profit)
            return
    
    def close(self, index, time, price):
        self.exit_index = index
        self.exit_time = time
        self.exit_price = price
        profit = price - self.entry_price
        if self.signal() == Signal.SHORT:
            profit *= -1
        self.profit = profit
        self.closed = True
        return
    
    def desc(self):
        s = 'profit:' + str(self.profit) +  ' entry:' + str(self.entry_price) + ' exit: ' + str(self.exit_price) + ' index:' + str(self.entry_time) + '...' + str(self.exit_time)
        return s
    
    @staticmethod 
    def position_num(trades):
        count = 0 
        for pos in trades:
            if pos.closed == False:
                count += 1
        return count
    
    @staticmethod 
    def summary(trades):
        num = 0
        sum = 0
        result = []
        win = 0
        profits = []
        acc = []
        time = []
        drawdown = None
        for pos in trades:
            if pos.closed == False:
                continue
            if pos.profit > 0:
                win += 1
            profits.append(pos.profit)
            sum += pos.profit
            acc.append(sum)
            time.append(pos.exit_time)
            if drawdown is None:
                drawdown = sum
            else:
                if sum < drawdown:
                    drawdown = sum   
            num += 1
            result.append([pos.signal(), pos.entry_index, str(pos.entry_time), pos.entry_price, pos.exit_index, pos.exit_time, pos.exit_price, pos.profit, pos.losscutted, pos.trailing_stopped ])
        if num == 0:
            return (None, None, None)
        else:
            profit_statics = {'fitness': (sum + drawdown), 'drawdown': drawdown, 'num': num, 'sum': sum, 'min': min(profits), 'max': max(profits), 'mean': (sum / num), 'stdev': np.std(profits), 'median': np.median(profits), 'win_rate': (float(win) / float(num))}
            columns = ['Long/Short', 'entry_index', 'entry_time', 'entry_price', 'exit_index', 'exit_time', 'exit_price', 'profit', 'losscutted', 'trailing_stopped']
            df = pd.DataFrame(data=result, columns=columns)
            return (df, (time, acc), profit_statics)
            
class TradeBotSim:
    def __init__(self, symbol: str, timeframe: str, trade_param: dict, time_filter: TimeFilter=None):
        self.symbol = symbol
        self.timeframe = timeframe
        self.trade_param = trade_param
        self.time_filter = time_filter
        self.positions = []
        
    def run(self, data: dict, begin_index: int):
        self.alldata = data
        self.data_size = len(data[Columns.TIME])
        self.current = begin_index

    def update(self):
        if self.current >= self.data_size - 1:
            return False
        data = Utils.sliceDict(self.alldata, 0, self.current)
        time = data[Columns.TIME]
        hi = data[Columns.HIGH]
        lo = data[Columns.LOW]
        cl = data[Columns.CLOSE]
        
        self.position_update(self.current, time[self.current], hi[self.current], lo[self.current], cl[self.current])
        if self.time_filter is not None:
            if self.time_filter.on(time[self.current]) == False:
                self.current += 1
                return True
        sig = self.detect_entry(data)
        if sig == Signal.LONG or sig == Signal.SHORT:
            if self.trade_param['trailing_stop'] == 0 or self.trade_param['target_profit'] == 0:
                self.close_all_positions(self.current, time[self.current], cl[self.current])
            else:
                self.close_not_trail_positions(self.current, time[self.current], cl[self.current])
                    
            #print('<Signal>', sig, self.current, time[self.current])
            if self.trade_param['position_max'] > PositionInfoSim.position_num(self.positions):
                self.entry(data, self.current, sig)
        self.current += 1
        return True
    
    def position_update(self, index, time, hi, lo, cl):
        for pos in self.positions:
            if pos.closed:
                continue
            pos.losscut(index, time, hi, lo, cl)
        
        trailing_stop = self.trade_param['trailing_stop']
        if trailing_stop == 0:
            return
        for pos in self.positions:
            if pos.closed:
                continue
            pos.trail(trailing_stop, index, time, cl)
            
    def open_position_count(self):
        count = 0
        for pos in self.positions:
            if not pos.closed:
                count += 1
        return count
    
    def detect_entry(self, data: dict):
        trend = data[Indicators.SUPERTREND]
        long_patterns = [[DOWN, UP], [0, UP]]
        short_patterns = [[UP, DOWN], [0, DOWN]]
        d = trend[-2:]
        for pat in long_patterns:
            if d == pat:
                return Signal.LONG
        for pat in short_patterns:
            if d == pat:
                return Signal.SHORT
        return None
        
    def entry(self, data: dict, index, signal):
        time = data[Columns.TIME]
        cl = data[Columns.CLOSE]
        price = cl[index]
        target = self.trade_param['target_profit']
        sl = self.trade_param['sl']
        #if sl == 0:
        #    atr = data[Indicators.ATR]
        #    sl = atr[index] * 2.0
        #    #print('Set Stoploss: ', sl)
        volume = self.trade_param['volume']
        if signal == Signal.LONG:
            typ = mt5.ORDER_TYPE_BUY
        else:
            typ = mt5.ORDER_TYPE_SELL
        pos = PositionInfoSim(self.symbol, typ, index, time[index], volume, 0, price, sl, target, 0)        
        #print('<Entry>', 'Signal', signal, index, time[index], 'price', price, 'sl', sl)
        self.positions.append(pos)
        
    def close_all_positions(self, index, time, price):
        for position in self.positions:
            if position.closed:
                continue
            position.close(index, time, price)
        
    def close_not_trail_positions(self, index, time, price):
        for position in self.positions:
            if position.closed:
                continue
            if position.profit_max is None:
                position.close(index, time, price)   
                position.timeupped = True
    
class Optimize:
    
    def __init__(self, name, symbol, timeframe, indicator_function, bot_class, time_filter: TimeFilter=None):
        self.name = name
        self.symbol = symbol
        self.timeframe = timeframe
        self.indicator_function = indicator_function
        self.bot_class = bot_class
        self.time_filter = time_filter
 
    def result_dir(self):
        dir = os.path.join('./result', self.name)
        return dir
    
    def graph_dir(self):
        dir = os.path.join('./profit_graph', self.name, self.symbol, self.timeframe)
        return dir
        
    def load_data(self, from_year: int, from_month: int, to_year: int, to_month: int):        
        self.from_year = from_year
        self.to_year = to_year
        loader = DataLoader()
        n, self.data = loader.load_data(self.symbol, self.timeframe, from_year, from_month, to_year, to_month)
        if n > 150:
            return True
        else:
            print('Data size small', n, self.symbol, self.timeframe)
            return False

    def code_to_technical_param(self, code):
        atr_window = code[0]
        atr_multiply = code[1]
        param = {'atr_window': atr_window, 'atr_multiply': atr_multiply, 'di_window': 25, 'adx_window': 25, 'polarity_window': 50}
        return param, ['atr_window', 'atr_multiply']
    
    def code_to_trade_param(self, code):
        sl = code[0]
        target_profit = code[1]
        trailing_stop = code[2]
        if trailing_stop == 0 or target_profit == 0:
            trailing_stop = target_profit = 0
        elif trailing_stop < target_profit:
            return None, None    
        param =  {'sl': sl, 'target_profit': target_profit, 'trailing_stop': trailing_stop, 'volume': 0.1, 'position_max': 5, 'timelimit': 0}
        return param, ['sl', 'target_profit', 'trailing_stop']
    
    def optimize_trade(self, gene_spaces, number, repeat=100, save_every=True, save_acc_graph=True):        
        columns1 = ['count', 'symbol', 'timeframe', 'year_begin', 'year_end']
        columns4 = ['fitness', 'drawdown', 'num', 'sum', 'min', 'max', 'mean', 'stdev', 'median', 'win_rate']
        technical = GeneticCode(gene_spaces[0])
        trade = GeneticCode(gene_spaces[1])
        result = []
        count = 0
        for i in range(repeat):
            data = self.data.copy()
            code0 = technical.create_code()
            technical_param, columns2 = self.code_to_technical_param(code0)
            self.indicator_function(data, technical_param)
            trade_param = None
            while True:
                code1 = trade.create_code()
                trade_param, columns3 = self.code_to_trade_param(code1)
                if trade_param is not None:
                    break
            #sim = TradeBotSim(self.symbol, self.timeframe, trade_param)
            sim = self.bot_class(self.symbol, self.timeframe, trade_param, time_filter=self.time_filter)
            sim.run(data, 150)
            i = 0
            while True:
                r = sim.update()
                if (i % 10000) == 0:
                    print(str(i) + ' / ' + str(len(data[Columns.TIME])))
                i += 1
                if r == False:
                    break
            trades = sim.positions
            if len(trades) > 1:
                (df, acc, statics) = PositionInfoSim.summary(trades)
                result.append([count, self.symbol, self.timeframe, self.from_year, self.to_year] + code0 + code1 + [statics['fitness'], statics['drawdown'], statics['num'], statics['sum'], statics['min'], statics['max'], statics['mean'], statics['stdev'], statics['median'], statics['win_rate']])
                print('#' + str(count), self.symbol, self.timeframe, 'profit', statics['sum'], 'drawdown', statics['drawdown'], 'num', statics['num'], 'win_rate', statics['win_rate'])    
                if save_acc_graph and statics['sum'] > 0:
                    fig, ax = makeFig(1, 1, (10, 4))
                    title = '#' + str(count) + '   profit_sum: ' + str(statics['sum']) + ' drawdown: ' + str(statics['drawdown'])
                    ax.plot(acc[0], acc[1], color='blue')
                    ax.set_title(title)
                    name = 'fig' + str(number) + '-' +  str(count) + '_profit_' + self.symbol + '_' + self.timeframe + '.png'
                    try:
                        plt.savefig(os.path.join(self.graph_dir(), name))   
                    except:
                        continue
                    plt.close()               
            count += 1
           
            if save_every:
                columns = columns1 + columns2 + columns3 + columns4
                df = pd.DataFrame(data=result, columns=columns)
                df = df.sort_values('fitness', ascending=False)
                try:
                    name = 'summary_' + self.symbol + '_' + self.timeframe + '_' + str(self.from_year) + '-' + str(self.to_year) + '_' + str(number) + '.xlsx'
                    df.to_excel( os.path.join(self.result_dir(), name))
                except:
                    continue
        if save_every == False:
            df = pd.DataFrame(data=result, columns=columns)
            df = df.sort_values('fitness', ascending=False)
            name = 'summary_' + self.symbol + '_' + self.timeframe + '_' + str(self.from_year) + '-' + str(self.to_year) + '_' + str(number) + '.xlsx'
            df.to_excel( os.path.join(self.result_dir(), name))
            
    def create_gene_space(self):
        symbol = self.symbol
        gene_space = None
        if symbol == 'NIKKEI' or symbol == 'DOW':
            r =  [GeneticCode.GeneFloat, 50, 500, 50]    
        elif symbol == 'NSDQ': #16000
            r = [GeneticCode.GeneFloat, 20, 200, 20]
        elif symbol == 'HK50':    
            r = [GeneticCode.GeneFloat, 50, 400, 50]
        elif symbol == 'USDJPY' or symbol == 'EURJPY':
            r = [GeneticCode.GeneFloat, 0.05, 0.5, 0.05]
        elif symbol == 'EURUSD': #1.0
            r = [GeneticCode.GeneFloat, 0.0005, 0.005, 0.0005]
        elif symbol == 'GBPJPY':
            r = [GeneticCode.GeneFloat, 0.05, 0.5, 0.05]
        elif symbol == 'AUDJPY': # 100
            r = [GeneticCode.GeneFloat, 0.025, 0.5, 0.025]
        elif symbol == 'XAUUSD': #2000
            r = [GeneticCode.GeneFloat, 0.5, 5.0, 0.5] 
        elif symbol == 'CL': # 70
            r = [GeneticCode.GeneFloat, 0.02, 0.2, 0.02] 
        else:
            raise Exception('Bad symbol')

        d = [0.0] + list(np.arange(r[1], r[2], r[3]))
        sl = r
        trailing_stop =  [GeneticCode.GeneList, d] 
        target = r

        technical_space = [
                        [GeneticCode.GeneInt,   10, 100, 10],     # atr_window
                        [GeneticCode.GeneFloat, 0.2, 4.0, 0.1]   # atr_multiply
        ]

        trade_space = [ 
                        sl,                                       # stoploss
                        target,                                   # target_profit
                        trailing_stop                             # trailing_stop    
                    ] 
        return technical_space, trade_space

    def run(self, number, repeat=100):
        os.makedirs(self.result_dir(), exist_ok=True)
        os.makedirs(self.graph_dir(), exist_ok=True)
        gene_space = self.create_gene_space()
        t0 = datetime.now()
        self.optimize_trade(gene_space, number, repeat=repeat, save_every=True)
        print('Finish, Elapsed time', datetime.now() - t0, self.symbol, self.timeframe)

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
        optimize = Optimize('supertrend', symbol, timeframe, indicators, TradeBotSim)
        if optimize.load_data(2020, 1, 2024, 2):
            optimize.run(number)
        else:
            print(symbol + ": No data")
               
if __name__ == '__main__':
    os.makedirs('./charts', exist_ok=True)
    os.makedirs('./result', exist_ok=True)
    main()
    #backtest('NIKKEI', 'M15')