

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
        reverse = (values[6] > 0)
        add_indicators(data, p)
        symbol = params['symbol']
        timeframe = params['timeframe']
        trades = supertrend_trade(data, stoploss, takeprofit, entry_horizon, exit_horizon, reverse)
        num, profit_acc, drawdown, maxv, win_rate = trade_summary(trades)
        print(symbol, timeframe, '>>>', values, reverse, '...', 'profit', profit_acc, 'drawdown', drawdown, 'win_rate', win_rate)
        if num > 0:
            return [profit_acc - drawdown]
        else:
            return [0.0]
        
def monthly(symbol, timeframe, gene_space, year, month):
    data = load_data(symbol, timeframe, [year], [month])
    inputs = {'data': data}
    ga = GA(GA_MAXIMIZE, gene_space, inputs, CROSSOVER_TWO_POINT, 0.3, 0.2)
    params = {'symbol': symbol, 'timeframe': timeframe}
    ga.setup(params)
    result = ga.run(7, 200, 50, should_plot=False)
    #result = ga.run(7, 200, 20, should_plot=False)
    
    print("=====")
    print(ga.description())
    print("=====")
 
    df = pd.DataFrame(data=result, columns=['atr_window', 'atr_multiply', 'sl', 'tp', 'entry_horizon', 'exit_horizon', 'reverse', 'fitness'])
    df = df[df['fitness'] > 0]
    #df.to_excel('./result/supertrend_invese_best_params_ga_' + symbol + '_' + timeframe + '.xlsx', index=False)
    return df

def all(symbol, timeframe, df_params):
    data0 = load_data(symbol, timeframe, [2020, 2021, 2022, 2023], range(1, 13))
    n = len(df_params)
    out = []
    for i in range(n):
        data = data0.copy()
        d = df_params.iloc[i, :]
        param = {'ATR': {'window': d.values[0], 'multiply': d.values[1]}}
        add_indicators(data, param)
        reverse = (d.values[6] > 0)
        trades = supertrend_trade(data, d.values[2], d.values[3], d.values[4], d.values[5], reverse)
        num, profit_acc, drawdown, maxv, win_rate = trade_summary(trades)
        if num > 0 and profit_acc > 0:        
            dd =[symbol, timeframe, d.values[0], d.values[1], d.values[2], d.values[3], d.values[4], d.values[5], d.values[6], profit_acc, drawdown, profit_acc + drawdown, num, win_rate]
            out.append(dd)
    columns = ['symbol', 'timeframe', 'atr_window', 'atr_multiply', 'sl', 'tp', 'entry_horizon', 'exit_horizon', 'reverse', 'profit', 'drawdown', 'profit+drawdown', 'num', 'win_rate']
    df = pd.DataFrame(data=out, columns=columns)
    df.to_excel('./result/supertrend_' + '_best_params_ga_' + symbol + '_' + timeframe + '.xlsx', index=False)
    return df

def optimize(symbol, timeframe, gene_space):
    logging.info('Start:  ' + symbol + ' '  +timeframe)
    logging.info(str(gene_space))
    t0 = datetime.now()
    dfs = []
    for year in [2020, 2021, 2022, 2023]:
        for month in range(1, 13):    
            df = monthly(symbol, timeframe, gene_space, year, month)
            dfs.append(df)
    df_param = pd.concat(dfs, ignore_index=True)
    df_param = df_param.drop(['fitness'], axis=1)
    df_param = df_param[~df_param.duplicated()]
    df_param = df_param.reset_index()
    all(symbol, timeframe, df_param)
    dt = datetime.now() - t0
    logging.info('Elapsed Time: ' + str(dt/ 60 / 60))
    print('Elapsed ', dt / 60 / 60, 'hours')
    
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
                [GeneInt, 0, 1, 1]                      # reverse                                     
            ]    
    optimize('NIKKEI', timeframe, gene_space)
    
def nasdaq(timeframe):
    gene_space = [
                [GeneInt, 10, 100, 10],                  # atr_window
                [GeneFloat, 0.5, 3.0, 0.5],             # atr_multiply 
                [GeneFloat, 20, 100, 10],               # losscut
                [GeneFloat, 0, 50, 10],        # takeprofit
                [GeneInt, 0, 1, 1],                     # entry_horizon
                [GeneInt, 0, 1, 1],                      # exit_horizon
                [GeneInt, 0, 1, 1]                      # reverse                                     
            ]                                     
            
    optimize('NSDQ', timeframe, gene_space)
    
def usdjpy(timeframe):
    gene_space = [
                [GeneInt, 10, 100, 10],          # atr_window
                [GeneFloat, 0.5, 3.0, 0.5],     # atr_multiply 
                [GeneFloat, 0.05, 0.5, 0.05],       # losscut
                [GeneFloat, 0, 0.05, 0.5, 0.05],        # takeprofit
                [GeneInt, 0, 1, 1],             # entry_horizon
                [GeneInt, 0, 1, 1],                      # exit_horizon
                [GeneInt, 0, 1, 1]                      # reverse                                     
            ]    
    optimize('USDJPY', timeframe, gene_space)

def main():
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
    
if __name__ == '__main__':
    main()