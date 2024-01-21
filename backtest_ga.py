

import random
import os
import sys
sys.path.append('../Libraries/trade')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from dateutil import tz
from common import Columns, Signal, Indicators
from technical import add_indicators, supertrend_trade, trade_summary, SL_TP_TYPE_NONE, SL_TP_TYPE_FIX, SL_TP_TYPE_AUTO
from candle_chart import CandleChart, makeFig, gridFig
from data_buffer import df2dic
from time_utils import TimeUtils
from utils import Utils
from gaclass_with_deap.GASolution import GASolution, GA_MAXIMIZE, CROSSOVER_TWO_POINT, GeneInt, GeneFloat, GeneList

JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc')  

RISK_REWARD_MIN = 0.3


import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('./log/backtest_ga.log')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

GENETIC_COLUMNS = ['atr_window', 'atr_multiply', 'sl_type', 'sl', 'tp_type', 'tp', 'entry_hold', 'timelimit', 'inverse']

def server_time_str_2_datetime(server_time_str_list, server_timezone, format='%Y-%m-%d %H:%M:%S'):
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

def data_filepath(symbol, timeframe, year, month):
    path = '../MarketData/Axiory/'
    dir_path = os.path.join(path, symbol, timeframe)
    name = symbol + '_' + timeframe + '_' + str(year) + '_' + str(month).zfill(2) + '.csv'
    filepath = os.path.join(dir_path, name)
    if os.path.isfile(filepath):
       return filepath 
    else:
        return None
    
def load_data(symbol, timeframe, years, months):
    dfs = []
    for year in years:
        for month in months:
            filepath = data_filepath(symbol, timeframe, year, month)
            if filepath is None:
                continue
            else:
                df = pd.read_csv(filepath)
                dfs.append(df)
    if len(dfs) == 0:
        return None
    df = pd.concat(dfs, ignore_index=True)
    dic = {}
    for column in df.columns:
        dic[column] = list(df[column].values)
    tzone = timezone(timedelta(hours=2))
    utc, jst = server_time_str_2_datetime(dic[Columns.TIME], tzone)
    dic[Columns.TIME] = utc
    dic[Columns.JST] = jst
    print(symbol, timeframe, 'Data size:', len(jst), jst[0], '-', jst[-1])
    return dic

class GA(GASolution):
    def evaluate(self, individual, inputs: dict, params: dict):
        data = inputs['data']
        values = self.individualValue(individual)
        p = {'ATR':{'window': values[0], 'multiply': values[1]}}
        atr_window = values[0]
        sl_type = values[2]
        stoploss = values[3]
        tp_type = values[4]
        tp = values[5]
        entry_hold = values[6]
        timelimit = values[7]
        inverse = values[8]
        add_indicators(data, p)
        symbol = params['symbol']
        timeframe = params['timeframe']
        trades = supertrend_trade(data, atr_window, sl_type, stoploss, tp_type, tp, entry_hold, timelimit, inverse)
        num, profit, drawdown, maxv, win_rate = trade_summary(trades)
        print(symbol, timeframe, '>>>', values, '...', 'profit', profit, 'drawdown', drawdown, 'win_rate', win_rate)
        if num > 0 and drawdown is not None:
            return [profit + drawdown]
        else:
            return [0.0]
        
        # 遺伝子コードの生成
    def createGeneticCode(self, gene_space: list):
        for _ in range(10):
            code = self.createCode(gene_space, RISK_REWARD_MIN)
            fitness = self.evaluate(code, self.inputs, self.params)
            if fitness[0] > 0:
                return code
            else:
                pass
                #print('   --> X')           
        return code    
    
    def createCode(self, gene_space, risk_reward_min: float):
        n = len(gene_space)
        while True:
            code = []
            for i in range(n):
                space = gene_space[i]
                value = self.gen_number(space)
                code.append(value)
                
            sl_type = code[2]    
            sl = code[3]
            tp_type = code[4]
            tp = code[5]
            if sl_type == SL_TP_TYPE_NONE or tp_type == SL_TP_TYPE_NONE:
                return code
            if sl == 0:
                return code
            if (tp / sl) >= risk_reward_min:
                return code
        
def ga_monthly(symbol, timeframe, gene_space, year, months, n_generation=4, n_population=30, n_top=20, init_code=[]):
    data = load_data(symbol, timeframe, [year], months)
    inputs = {'data': data}
    ga = GA(GA_MAXIMIZE, gene_space, inputs, CROSSOVER_TWO_POINT, 0.3, 0.2)
    params = {'symbol': symbol, 'timeframe': timeframe}
    ga.setup(params)
    result = ga.run(n_generation, n_population, n_top, should_plot=False, initial_code=init_code)
    #result = ga.run(3, 20, 5, should_plot=False)
    
    print("=====")
    print(ga.description())
    print("=====")
 
    columns = GENETIC_COLUMNS + ['fitness']
    df = pd.DataFrame(data=result, columns=columns)
    df = df[df['fitness'] > 0]
    #df.to_excel('./result/supertrend_invese_best_params_ga_' + symbol + '_' + timeframe + '.xlsx', index=False)
    return df

def season(symbol, timeframe, df_params, years, months):
    data0 = load_data(symbol, timeframe, years, months)
    n = len(df_params)
    out = []
    for i in range(n):
        data = data0.copy()
        d = df_params.iloc[i, :]
        atr_window = d['atr_window']
        atr_multiply = d['atr_multiply']
        sl_type = d['sl_type']
        sl = d['sl']
        tp_type = d['tp_type']
        tp = d['tp']
        entry_hold = d['entry_hold']
        timelimit = d['timelimit']
        param = {'ATR': {'window': atr_window, 'multiply': atr_multiply}}
        add_indicators(data, param)
        inverse = d['inverse']
        trades = supertrend_trade(data, atr_window, sl_type, sl, tp_type, tp, entry_hold, timelimit, inverse)
        num, profit_acc, drawdown, maxv, win_rate = trade_summary(trades)
        if num > 0 : #and profit_acc > 0:        
            dd =[symbol, timeframe, atr_window, atr_multiply, sl_type, sl, tp_type, tp, entry_hold, timelimit, inverse, profit_acc, drawdown, profit_acc + drawdown, num, win_rate]
            out.append(dd)
    columns = ['symbol', 'timeframe'] + GENETIC_COLUMNS + ['profit', 'drawdown', 'fitness', 'num', 'win_rate']
    df = pd.DataFrame(data=out, columns=columns)
    return df

def optimize0(symbol, timeframe, gene_space):
    logging.info(str(gene_space))
    data0 = load_data(symbol, timeframe, [2020, 2021, 2022, 2023, 2024], range(1, 13))
    inputs = {'data': data0.copy()}
    ga = GA(GA_MAXIMIZE, gene_space, inputs, CROSSOVER_TWO_POINT, 0.3, 0.2)
    params = {'symbol': symbol, 'timeframe': timeframe}
    ga.setup(params)
    count = 0
    codes = []
    t0 = datetime.now()
    while count < 100:
        code = ga.createCode(gene_space)
        fitness = ga.evaluate(code, inputs, params)
        if fitness[0] > 0:
            codes.append([symbol , timeframe] + code + fitness)
            count += 1
            print(count, datetime.now() - t0, symbol, timeframe, fitness, code)
            t0 = datetime.now()
    columns = ['symbol', 'timeframe'] + GENETIC_COLUMNS + ['fitness']
    df = pd.DataFrame(data=codes, columns=columns)
    df = df.sort_values('fitness', ascending=False)
    df.to_excel('./result/supertrend_optimize0_rev2_' + symbol + '_' + timeframe + '.xlsx', index=False)
    return df

def optimize1(symbol, timeframe, gene_space):
    logging.info(str(gene_space))
    data0 = load_data(symbol, timeframe, [2020, 2021, 2022, 2023], range(1, 13))
    inputs = {'data': data0.copy()}
    ga = GA(GA_MAXIMIZE, gene_space, inputs, CROSSOVER_TWO_POINT, 0.3, 0.2)
    params = {'symbol': symbol, 'timeframe': timeframe}
    ga.setup(params)
    result = ga.run(7, 200, 50, should_plot=False)
    #result = ga.run(7, 200, 20, should_plot=False)
    
    print("=====")
    print(ga.description())
    print("=====")
    columns = GENETIC_COLUMNS + ['fitness']
    df = pd.DataFrame(data=result, columns=columns)
    df = df[df['fitness'] > 0]
    df.to_excel('./result/supertrend_ga_optimize1_rev2_' + symbol + '_' + timeframe + '.xlsx', index=False)
    return df


def optimize2(symbol, timeframe, gene_space):    
    logging.info(str(gene_space))
    dfs = []
    for year in [2020, 2021, 2022, 2023]:
        for months in [range(1, 4), range(4, 7), range(7, 10), range(10, 13)]:
            df = ga_monthly(symbol, timeframe, gene_space, year, months)
            dfs.append(df)            
    df_param = pd.concat(dfs, ignore_index=True)
    df_param = df_param.reset_index() 
    df_param = df_param.sort_values('fitness', ascending=False)
    if len(df_param) > 100:
        df_param = df_param.iloc[:100, :]
    result = season(symbol, timeframe, df_param, [2020, 2021, 2022, 2023], range(1, 13))
    result.to_excel('./result/supertrend_ga_optimize2_rev2_' + symbol + '_' + timeframe + '.xlsx', index=False)
   
   
def optimize3(symbol, timeframe, gene_space):    
    logging.info(str(gene_space))
    total = []
    for year in [2020, 2021, 2022, 2023]:
        for i in range(2):
            if i == 0:
                months = range(1, 7)
            else:
                months = range(7, 13)
            dfs = []
            for month in months:    
                df = ga_monthly(symbol, timeframe, gene_space, year, [month])
                dfs.append(df)            
            df_p = pd.concat(dfs, ignore_index=True)
            df_p = df_p[df_p['fitness'] > 0]
            df_p = df_p[~df_p.duplicated()]
            df_p = df_p.reset_index()
            if len(df_p) > 0:
                df = season(symbol, timeframe, df_p, [year], months)
                total.append(df)
    df_param = pd.concat(total, ignore_index=True)
    df_param = df_param.reset_index() 
    df_param = df_param.sort_values('fitness', ascending=False)
    if len(df_param) > 20:
        df_param = df_param.iloc[:20, :]
    result = season(symbol, timeframe, df_param, [2020, 2021, 2022, 2023], range(1, 13))
    result.to_excel('./result/supertrend_ga_optimize3_rev2_' + symbol + '_' + timeframe + '.xlsx', index=False)
    
def df2list(df):
    out = []
    for value in df.values:
        out.append(list(value))
    return out
    
def optimize4(symbol, timeframe, gene_space):
    year_month = []
    for year in range(2020, 2025):
        for month in range(1, 13):
            filepath = data_filepath(symbol, timeframe, year, month)
            if filepath is None:
                continue
            year_month.append([year, month])    
    np.random.shuffle(year_month)
    dfs = []
    for i in range(6):
        year, month = year_month[i]
        df = ga_monthly(symbol, timeframe, gene_space, year, [month], n_generation=5, n_population=40, n_top=10)
        dfs.append(df)
        
    df_param = pd.concat(dfs, ignore_index=True)
    df_param = df_param.reset_index() 
    df_param = df_param.sort_values('fitness', ascending=False)
    if len(df_param) > 60:
        df_param = df_param.iloc[:60, :]
    df_param = df_param.drop(['index', 'fitness'], axis=1)
    init_code = df2list(df_param)
    for i in range(6, len(year_month)):
        year, month = year_month[i]
        df_param = ga_monthly(symbol, timeframe, gene_space, year, [month], n_generation=5, n_population=40, n_top=20, init_code=init_code)
        df_param = df_param.drop(['fitness'], axis=1)
        init_code = df2list(df_param)
    df = df.reset_index() 
    df = df.sort_values('fitness', ascending=False)    
    df = df.iloc[:10, :]
    df = season(symbol, timeframe, df, range(2020, 2025), range(1, 13))
    df.to_excel('./result/supertrend_ga_optimize4_rev3_' + symbol + '_' + timeframe + '.xlsx', index=False)
 
def optimize5(symbol, timeframe, gene_space):
    year_month = []
    for year in range(2020, 2025):
        for month in range(1, 13):
            filepath = data_filepath(symbol, timeframe, year, month)
            if filepath is None:
                continue
            year_month.append([year, month])    
    np.random.shuffle(year_month)
    
    year, month = year_month[0]
    df_param = ga_monthly(symbol, timeframe, gene_space, year, [month], n_generation=5, n_population=100, n_top=50)
    df_param = df_param.drop(['index', 'fitness'], axis=1)
    init_code = df2list(df_param)
    for i in range(2, len(year_month)):
        year, month = year_month[i]
        df_param = ga_monthly(symbol, timeframe, gene_space, year, [month], n_generation=5, n_population=60, n_top=50, init_code=init_code)
        df_param = df_param.drop(['fitness'], axis=1)
        init_code = df2list(df_param)
    df_param = df_param.reset_index() 
    df_param = df_param.sort_values('fitness', ascending=False)    
    df_param = df_param.ilock[:5, :]
    df = season(symbol, timeframe, df_param, range(2020, 2025), range(1, 13))
    df.to_excel('./result/supertrend_ga_optimize5_rev3_' + symbol + '_' + timeframe + '.xlsx', index=False)   
    
def parse_timeframe(timeframe):
    tf = timeframe.lower()
    num = int(tf[1:])
    if tf[0] == 'm':
        return (num < 30)
    else:
        return False


def make_gene_space(symbol, timeframe):
    gene_space = None
    if symbol == 'NIKKEI' or symbol == 'DOW':
        losscut =  [GeneFloat, 100, 300, 10]    
    elif symbol == 'NSDQ': #16000
        losscut = [GeneFloat, 20, 100, 10]
    elif symbol == 'HK50':    
        losscut = [GeneFloat, 50, 200, 10]
    elif symbol == 'USDJPY' or symbol == 'EURJPY':
        losscut = [GeneFloat, 0.05, 0.5, 0.05]
    elif symbol == 'EURUSD': #1.0
        losscut = [GeneFloat, 0.0005, 0.005, 0.0005]
    elif symbol == 'GBPJPY':
        losscut = [GeneFloat, 0.05, 0.5, 0.05]
    elif symbol == 'AUDJPY': # 100
        losscut = [GeneFloat, 0.025, 0.5, 0.025]
    elif symbol == 'XAUUSD': #2000
        losscut = [GeneFloat, 0.5, 5.0, 0.5] 
    elif symbol == 'CL': # 70
        losscut = [GeneFloat, 0.02, 0.5, 0.2] 
    else:
        raise Exception('Bad symbol')
    
    takeprofit = [GeneFloat, losscut[1]/ 4, losscut[2] * 4, losscut[3]]
    
    gene_space = [
                    [GeneInt, 10, 100, 10],                # atr_window
                    [GeneFloat, 0.4, 4.0, 0.1],            # atr_multiply 
                    [GeneInt, 0, 2, 1],                    # losscut type 0: No, 1: Auto 2: Fix
                    losscut,                               # losscut
                    [GeneInt, 0, 1, 1],                    # takeprofit type 0: No, 1: Fix
                    takeprofit,                            # takeprofit
                    [GeneInt, 0, 1, 2],                    # entry_hold
                    [GeneInt, 5, 40, 5],                   # timeup
                    [GeneInt, 0, 1, 1]                     # inverse                                     
                ]   
    return gene_space

def optimize(symbol, timeframe, mode):
    symbol = symbol.upper()
    timeframe = timeframe.upper()
    mode = int(mode)
    gene_space = make_gene_space(symbol, timeframe)
    if mode == 0:
        optimize0(symbol, timeframe, gene_space)
    if mode == 1:
        optimize1(symbol, timeframe, gene_space)
    elif mode == 2:
        optimize2(symbol, timeframe, gene_space)
    elif mode == 3:
        optimize3(symbol, timeframe, gene_space)
    elif mode == 4:
        optimize4(symbol, timeframe, gene_space)    
    elif mode == 5:
        optimize4(symbol, timeframe, gene_space)    
    else:
        raise Exception("Bad mode")
    
def series(symbols, timeframe, mode):
    for symbol in symbols:
        t0 = datetime.now()
        try:
            optimize(symbol, timeframe, mode)
            print('Finish, Elapsed time', datetime.now() - t0, symbol, timeframe, mode)
        except Exception as e:
            print(e)
            print('Error in ', symbol)
            continue
        
def all(timeframe, mode):
     symbols = ['NIKKEI', 'DOW', 'NSDQ', 'XAUUSD', 'USDJPY', 'CL', 'EURJPY', 'EURUSD', 'GBPJPY', 'AUDJPY', 'XAUUSD']
     series(symbols, timeframe, mode)
        
        
def fx(timeframe, mode):
    symbols = ['USDJPY', 'EURJPY', 'EURUSD', 'GBPJPY', 'AUDJPY']
    series(symbols, timeframe, mode)

def stock(timeframe, mode):
     symbols = ['NIKKEI', 'DOW', 'NSDQ']
     series(symbols, timeframe, mode)
     
def comodity(timeframe, mode):
     symbols = ['XAUUSD', 'CL']
     series(symbols, timeframe, mode)
        
def main():
    t0 = datetime.now()
    args = sys.argv
    #args = ['', 'USDJPY', 'H4', 4]
    if len(args) < 3:
        raise Exception('Bad parameter')

    symbol = args[1]
    symbol = symbol.upper()
    timeframe = args[2]
    if len(args) > 3:
        mode = args[3]
    else:
        mode = 4
    if symbol == 'ALL':
        all(timeframe, mode)
    elif symbol == 'FX':
        fx(timeframe, mode)
    elif symbol == 'STOCK':
        stock(timeframe, mode)
    elif symbol == 'COMODITY':
        comodity(timeframe, mode)
    else:    
        optimize(symbol, timeframe, mode)
        print('Finish, Elapsed time', datetime.now() - t0, symbol, timeframe, mode)

if __name__ == '__main__':
    main()