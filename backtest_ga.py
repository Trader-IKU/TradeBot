

import random
import os
import sys
sys.path.append('../Libraries/trade')

import numpy as np
import pandas as pd
import pytz
from datetime import datetime, timedelta
from common import Columns, Signal, Indicators
from technical import add_indicators, supertrend_trade, trade_summary
from candle_chart import CandleChart, makeFig, gridFig
from data_buffer import df2dic
from time_utils import TimeUtils
from utils import Utils
from gaclass_with_deap.GASolution import GASolution, GA_MAXIMIZE, CROSSOVER_TWO_POINT, GeneInt, GeneFloat, GeneList

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('./log/backtest_ga.log')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def utc_str_2_jst(utc_str_list, format='%Y-%m-%d %H:%M:%S'):
    out = []
    for utc_str in utc_str_list:
        utc = datetime.strptime(utc_str, format) 
        utc = pytz.timezone('UTC').localize(utc)
        jst = utc.astimezone(pytz.timezone('Asia/Tokyo'))        
        out.append(jst)
    return out

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
    jst = utc_str_2_jst(dic[Columns.TIME])
    dic[Columns.TIME] = jst
    print(symbol, timeframe, 'Data size:', len(jst), jst[0], '-', jst[-1])
    return dic

class GA(GASolution):
    def evaluate(self, individual, inputs: dict, params: dict):
        data = inputs['data']
        values = self.individualValue(individual)
        p = {'ATR':{'window': values[0], 'multiply': values[1]}}
        stoploss = values[2]
        takeprofit = values[3]
        entry_horizon = values[4]
        exit_horizon = values[5]
        inverse = values[6] 
        add_indicators(data, p)
        symbol = params['symbol']
        timeframe = params['timeframe']
        trades = supertrend_trade(data, stoploss, takeprofit, entry_horizon, exit_horizon, inverse)
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
        
        
def ga_monthly(symbol, timeframe, gene_space, year, month):
    data = load_data(symbol, timeframe, [year], [month])
    inputs = {'data': data}
    ga = GA(GA_MAXIMIZE, gene_space, inputs, CROSSOVER_TWO_POINT, 0.3, 0.2)
    params = {'symbol': symbol, 'timeframe': timeframe}
    ga.setup(params)
    result = ga.run(5, 50, 20, should_plot=False)
    #result = ga.run(3, 20, 5, should_plot=False)
    
    print("=====")
    print(ga.description())
    print("=====")
 
    df = pd.DataFrame(data=result, columns=['atr_window', 'atr_multiply', 'sl', 'tp', 'entry_horizon', 'exit_horizon', 'inverse', 'fitness'])
    df = df[df['fitness'] > 0]
    #df.to_excel('./result/supertrend_invese_best_params_ga_' + symbol + '_' + timeframe + '.xlsx', index=False)
    return df

def optimize2level(symbol, timeframe, gene_space):    
    logging.info(str(gene_space))
    dfs = []
    for year in [2020, 2021, 2022, 2023]:
        for month in range(1, 13):    
            df = ga_monthly(symbol, timeframe, gene_space, year, month)
            dfs.append(df)
    df_param = pd.concat(dfs, ignore_index=True)
    df_param = df_param.drop(['fitness'], axis=1)
    df_param = df_param[~df_param.duplicated()]
    df_param = df_param.reset_index()
    result = season(symbol, timeframe, df_param, [2020, 2021, 2022, 2023], range(1, 13))
    result.to_excel('./result/supertrend_' + '_best_params_ga_' + symbol + '_' + timeframe + '.xlsx', index=False)

    
def season(symbol, timeframe, df_params, years, months):
    data0 = load_data(symbol, timeframe, years, months)
    n = len(df_params)
    out = []
    for i in range(n):
        data = data0.copy()
        d = df_params.iloc[i, :]
        atr_window = d['atr_window']
        atr_multiply = d['atr_multiply']
        sl = d['sl']
        tp = d['tp']
        entry_horizon = d['entry_horizon']
        exit_horizon = d['exit_horizon']
        param = {'ATR': {'window': atr_window, 'multiply': atr_multiply}}
        add_indicators(data, param)
        inverse = (d['inverse'] > 0)
        trades = supertrend_trade(data, sl, tp, entry_horizon, exit_horizon, inverse)
        num, profit_acc, drawdown, maxv, win_rate = trade_summary(trades)
        if num > 0 : #and profit_acc > 0:        
            dd =[symbol, timeframe, atr_window, atr_multiply, sl, tp, entry_horizon, exit_horizon, inverse, profit_acc, drawdown, profit_acc + drawdown, num, win_rate]
            out.append(dd)
    columns = ['symbol', 'timeframe', 'atr_window', 'atr_multiply', 'sl', 'tp', 'entry_horizon', 'exit_horizon', 'inverse', 'profit', 'drawdown', 'profit+drawdown', 'num', 'win_rate']
    df = pd.DataFrame(data=out, columns=columns)
    return df
    
def optimize3level(symbol, timeframe, gene_space):    
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
                df = ga_monthly(symbol, timeframe, gene_space, year, month)
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
    if len(df_param) > 10:
        df_param = df_param.iloc[:10, :]
    result = season(symbol, timeframe, df_param, [2020, 2021, 2022, 2023], range(1, 13))
    result.to_excel('./result/supertrend_ga_3level_' + symbol + '_' + timeframe + '.xlsx', index=False)
    
def optimize1level(symbol, timeframe, gene_space):
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
 
    df = pd.DataFrame(data=result, columns=['atr_window', 'atr_multiply', 'sl', 'tp', 'entry_horizon', 'exit_horizon', 'inverse', 'fitness'])
    df = df[df['fitness'] > 0]
    df.to_excel('./result/supertrend_oneshot_ga_' + symbol + '_' + timeframe + '.xlsx', index=False)
    return df
    
    
def parse_timeframe(timeframe):
    tf = timeframe.lower()
    num = int(tf[1:])
    if tf[0] == 'm':
        return (num < 30)
    else:
        return False
            
def nikkei(timeframe):
    gene_space = [
                [GeneInt, 10, 100, 10],                  # atr_window
                [GeneFloat, 0.5, 3.0, 0.5],             # atr_multiply 
                [GeneFloat, 40, 300, 10],               # losscut
                [GeneFloat, 0, 200, 10],        # takeprofit
                [GeneInt, 0, 1, 1],                     # entry_horizon
                [GeneInt, 0, 1, 1],                      # exit_horizon
                [GeneInt, 0, 1, 1]                      # inverse                                     
            ]    
    optimize3level('NIKKEI', timeframe, gene_space)
    
def nasdaq(timeframe):
    gene_space = [
                [GeneInt, 10, 100, 10],                  # atr_window
                [GeneFloat, 0.5, 3.0, 0.5],             # atr_multiply 
                [GeneFloat, 20, 100, 10],               # losscut
                [GeneFloat, 0, 50, 10],        # takeprofit
                [GeneInt, 0, 1, 1],                     # entry_horizon
                [GeneInt, 0, 1, 1],                      # exit_horizon
                [GeneInt, 0, 1, 1]                      # inverse                                     
            ]                                     
            
    optimize3level('NSDQ', timeframe, gene_space)
    
def usdjpy(timeframe):
    gene_space = [
                [GeneInt, 10, 100, 10],          # atr_window
                [GeneFloat, 0.5, 3.0, 0.5],     # atr_multiply 
                [GeneFloat, 0.05, 0.5, 0.05],       # losscut
                [GeneFloat, 0, 0.05, 0.5, 0.05],        # takeprofit
                [GeneInt, 0, 1, 1],             # entry_horizon
                [GeneInt, 0, 1, 1],                      # exit_horizon
                [GeneInt, 0, 1, 1]                      # inverse                                     
            ]    
    optimize3level('USDJPY', timeframe, gene_space)

def main():
    t0 = datetime.now()
    args = sys.argv
    symbol = args[1]
    timeframe = args[2]
    if symbol.lower() == 'nikkei':
        nikkei(timeframe)
    elif symbol.lower() == 'usdjpy':
        usdjpy(timeframe)
    elif symbol.lower() == 'nasdaq':
        nasdaq(timeframe)
    else:
        print('Error bad argument', args)
        
    dt = datetime.now() - t0
    logging.info('Elapsed Time: ' + str(dt))
    print('Elapsed ', dt)
    
if __name__ == '__main__':
    main()