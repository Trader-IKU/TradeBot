

import random
import os
import sys
sys.path.append('../Libraries/trade')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from dateutil import tz
from common import Columns, Signal, Indicators
from technical import add_indicators, supertrend_trade, trade_summary
from candle_chart import CandleChart, makeFig, gridFig
from data_buffer import df2dic
from time_utils import TimeUtils
from utils import Utils
from gaclass_with_deap.GASolution import GASolution, GA_MAXIMIZE, CROSSOVER_TWO_POINT, GeneInt, GeneFloat, GeneList

JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc')  


import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('./log/backtest_ga.log')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

GENETIC_COLUMNS = ['atr_window', 'atr_multiply', 'sl_type', 'sl', 'tp_type', 'risk_reward', 'entry_horizon', 'exit_horizon', 'timeup_minutes', 'inverse']

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

def load_data(symbol, timeframe, years, months):
    path = '../MarketData/Axiory/'
    dir_path = os.path.join(path, symbol, timeframe)
    dfs = []
    for year in years:
        for month in months:
            name = symbol + '_' + timeframe + '_' + str(year) + '_' + str(month).zfill(2) + '.csv'
            try:
                d = pd.read_csv(os.path.join(dir_path, name))
                dfs.append(d[[Columns.TIME, Columns.OPEN, Columns.HIGH, Columns.LOW, Columns.CLOSE]])
            except:
                print('Error in', name)
                continue
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
        risk_reward = values[5]
        entry_horizon = values[6]
        exit_horizon = values[7]
        timeup_minutes = values[8]
        inverse = values[9] 
        add_indicators(data, p)
        symbol = params['symbol']
        timeframe = params['timeframe']
        trades = supertrend_trade(data, atr_window, sl_type, stoploss, tp_type, risk_reward, entry_horizon, exit_horizon, timeup_minutes, inverse)
        num, profit_acc, drawdown, maxv, win_rate = trade_summary(trades)
        print(symbol, timeframe, '>>>', values, '...', 'profit', profit_acc, 'drawdown', drawdown, 'win_rate', win_rate)
        if num > 0 and drawdown is not None:
            return [profit_acc + drawdown]
        else:
            return [0.0]
        
        # 遺伝子コードの生成
    def createGeneticCode(self, gene_space: list):
        for _ in range(10):
            code = self.createCode(gene_space)
            fitness = self.evaluate(code, self.inputs, self.params)
            if fitness[0] > 0:
                return code
            else:
                print('   --> X')
            
        return code    
        
        
def ga_monthly(symbol, timeframe, gene_space, year, months):
    data = load_data(symbol, timeframe, [year], months)
    inputs = {'data': data}
    ga = GA(GA_MAXIMIZE, gene_space, inputs, CROSSOVER_TWO_POINT, 0.3, 0.2)
    params = {'symbol': symbol, 'timeframe': timeframe}
    ga.setup(params)
    result = ga.run(4, 50, 30, should_plot=False)
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
        risk_reward = d['risk_reward']
        entry_horizon = d['entry_horizon']
        exit_horizon = d['exit_horizon']
        timeup_minutes = d['timeup_minutes']
        param = {'ATR': {'window': atr_window, 'multiply': atr_multiply}}
        add_indicators(data, param)
        inverse = d['inverse']
        trades = supertrend_trade(data, atr_window, sl_type, sl, tp_type, risk_reward, entry_horizon, exit_horizon, timeup_minutes, inverse)
        num, profit_acc, drawdown, maxv, win_rate = trade_summary(trades)
        if num > 0 : #and profit_acc > 0:        
            dd =[symbol, timeframe, atr_window, atr_multiply, sl_type, sl, tp_type, risk_reward, entry_horizon, exit_horizon, timeup_minutes, inverse, profit_acc, drawdown, profit_acc + drawdown, num, win_rate]
            out.append(dd)
    columns = ['symbol', 'timeframe'] + GENETIC_COLUMNS + ['profit', 'drawdown', 'fitness', 'num', 'win_rate']
    df = pd.DataFrame(data=out, columns=columns)
    return df

def optimize0(symbol, timeframe, gene_space):
    logging.info(str(gene_space))
    data0 = load_data(symbol, timeframe, [2020, 2021, 2022, 2023], range(1, 13))
    inputs = {'data': data0.copy()}
    ga = GA(GA_MAXIMIZE, gene_space, inputs, CROSSOVER_TWO_POINT, 0.3, 0.2)
    params = {'symbol': symbol, 'timeframe': timeframe}
    ga.setup(params)
    count = 0
    codes = []
    while count < 200:
        code = ga.createCode(gene_space)
        fitness = ga.evaluate(code, inputs, params)
        if fitness[0] > 0:
            codes.append([symbol , timeframe] + code + fitness)
            count += 1
            print(symbol, timeframe, fitness, code)
    columns = ['symbol', 'timeframe'] + GENETIC_COLUMNS + ['fitness']
    df = pd.DataFrame(data=codes, columns=columns)
    df = df.sort_values('fitness', ascending=False)
    df.to_excel('./result/supertrend_optimize_rev0' + symbol + '_' + timeframe + '.xlsx', index=False)
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
    df.to_excel('./result/supertrend_oneshot_ga_rev10' + symbol + '_' + timeframe + '.xlsx', index=False)
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
    result.to_excel('./result/supertrend_ga_level2_rev10_' + symbol + '_' + timeframe + '.xlsx', index=False)
   
   
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
    result.to_excel('./result/supertrend_ga_level3_rev10_' + symbol + '_' + timeframe + '.xlsx', index=False)
    
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
        gene_space = [
                [GeneInt, 10, 100, 10],                # atr_window
                [GeneFloat, 0.4, 3.0, 0.2],            # atr_multiply 
                [GeneInt, 0, 2, 1],                    # losscut type 0: No, 1: Auto 2: Fix
                [GeneFloat, 100, 300, 10],             # losscut
                [GeneInt, 0, 1, 1],                    # takeprofit type 0: No, 1: Fix
                [GeneFloat, 0, 2.0, 0.1],              # risk_reward
                [GeneInt, 0, 1, 1],                    # entry_horizon
                [GeneInt, 0, 1, 1],                    # exit_horizon
                [GeneInt, 0, 480, 30],                 # timeup_minutes
                [GeneInt, 0, 1, 1]                     # inverse                                     
            ]
    elif symbol == 'NSDQ':
        gene_space = [
                [GeneInt, 10, 100, 10],                # atr_window
                [GeneFloat, 0.4, 3.0, 0.2],            # atr_multiply 
                [GeneInt, 0, 2, 1],                    # losscut type 0: No, 1: Auto 2: Fix
                [GeneFloat, 20, 100, 10],              # losscut
                [GeneInt, 0, 1, 1],                    # takeprofit type 0: No, 1: Fix
                [GeneFloat, 0, 2.0, 0.1],              # risk_reward
                [GeneInt, 0, 1, 1],                    # entry_horizon
                [GeneInt, 0, 1, 1],                    # exit_horizon
                [GeneInt, 0, 480, 30],                 # timeup_minutes
                [GeneInt, 0, 1, 1]                     # inverse                                     
            ]   
    elif symbol == 'HK50':
        gene_space = [
                [GeneInt, 10, 100, 10],                # atr_window
                [GeneFloat, 0.4, 3.0, 0.2],            # atr_multiply
                [GeneInt, 0, 2, 1],                    # losscut type 0: No, 1: Auto 2: Fix
                [GeneFloat, 50, 200, 10],              # losscut
                [GeneInt, 0, 1, 1],                    # takeprofit type 0: No, 1: Fix
                [GeneFloat, 0, 2.0, 0.1],              # risk_reward
                [GeneInt, 0, 1, 1],                    # entry_horizon
                [GeneInt, 0, 1, 1],                    # exit_horizon
                [GeneInt, 0, 480, 30],                 # timeup_minutes
                [GeneInt, 0, 1, 1]                     # inverse                                     
            ]   
             
    elif symbol == 'USDJPY':
        gene_space = [
                [GeneInt, 10, 100, 10],                 # atr_window
                [GeneFloat, 0.4, 3.0, 0.2],             # atr_multiply
                [GeneInt, 0, 2, 1],                     # losscut type 0: No, 1: Auto 2: Fix 
                [GeneFloat, 0.05, 0.5, 0.05],           # losscut
                [GeneInt, 0, 1, 1],                     # takeprofit type 0: No, 1: Fix
                [GeneFloat, 0, 2.0, 0.1],               # risk_reward
                [GeneInt, 0, 1, 1],                     # entry_horizon
                [GeneInt, 0, 1, 1],                     # exit_horizon
                [GeneInt, 0, 480, 30],                  # timeup_minutes
                [GeneInt, 0, 1, 1]                      # inverse                                      
            ]    
    elif symbol == 'GBPJPY':
        gene_space = [
                [GeneInt, 10, 100, 10],                 # atr_window
                [GeneFloat, 0.4, 3.0, 0.2],             # atr_multiply
                [GeneInt, 0, 2, 1],                     # losscut type 0: No, 1: Auto 2: Fix 
                [GeneFloat, 0.05, 0.5, 0.05],           # losscut
                [GeneInt, 0, 1, 1],                     # takeprofit type 0: No, 1: Fix
                [GeneFloat, 0, 2.0, 0.1],               # risk_reward
                [GeneInt, 0, 1, 1],                     # entry_horizon
                [GeneInt, 0, 1, 1],                     # exit_horizon
                [GeneInt, 0, 480, 30],                  # timeup_minutes
                [GeneInt, 0, 1, 1]                      # inverse                                      
            ]    
    elif symbol == 'AUDJPY':
        gene_space = [
                [GeneInt, 10, 100, 10],                 # atr_window
                [GeneFloat, 0.4, 3.0, 0.2],             # atr_multiply
                [GeneInt, 0, 2, 1],                     # losscut type 0: No, 1: Auto 2: Fix 
                [GeneFloat, 0.025, 0.5, 0.025],         # losscut
                [GeneInt, 0, 1, 1],                     # takeprofit type 0: No, 1: Fix
                [GeneFloat, 0, 2.0, 0.1],               # risk_reward
                [GeneInt, 0, 1, 1],                     # entry_horizon
                [GeneInt, 0, 1, 1],                     # exit_horizon
                [GeneInt, 0, 480, 30],                  # timeup_minutes
                [GeneInt, 0, 1, 1]                      # inverse                                      
            ]
    else:
        raise Exception('Bad symbol')   
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
    else:
        raise Exception("Bad mode")
      
def main():
    t0 = datetime.now()
    args = sys.argv
    #args = ['', 'USDJPY', 'H4', 3]
    if len(args) < 4:
        raise Exception('Bad parameter')
    symbol = args[1]
    timeframe = args[2]
    mode = args[3]
    optimize(symbol, timeframe, mode)
    
    print('Finish, Elapsed time', datetime.now() - t0, symbol, timeframe, mode)
    
    
if __name__ == '__main__':
    main()