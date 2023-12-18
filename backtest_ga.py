

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
from gaclass_with_deap.GASolution import GASolution, GA_MAXIMIZE, CROSSOVER_ONE_POINT, GeneInt, GeneFloat


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
    print('Data size:', len(jst), jst[0], '-', jst[-1])
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
        add_indicators(data, p)
        inverse = params['inverse']
        trades = supertrend_trade(data, stoploss, takeprofit, entry_horizon, exit_horizon, inverse)
        num, profit_acc, drawdown, maxv = trade_summary(trades)
        print(p, values, inverse, '...', 'profit_acc', profit_acc, 'drawdown', drawdown)
        return [profit_acc - drawdown]
        
def main(symbol, timeframe):
    data = load_data(symbol, timeframe, [2020, 2021, 2022, 2023], range(1, 13))
    random.seed(1)
    gene_space = [
                    [GeneInt, 10, 50, 10],            # atr_window
                    [GeneFloat, 0.5, 3.0, 0.5],     # atr_multiply 
                    [GeneFloat, 50, 300, 50],       # losscut
                    [GeneFloat, 0, 300, 50],        # takeprofit
                    [GeneInt, 0, 2, 1],             # entry_horizon
                    [GeneInt, 0, 2, 1]              # exit_horizon                                     
                ]
    
    inputs = {'data': data}
    ga = GA(GA_MAXIMIZE, gene_space, inputs, CROSSOVER_ONE_POINT, 0.4, 0.3)
    params = {'inverse': True}
    ga.setup(params)
    result = ga.run(10, 10, 5)
    
    print("=====")
    print(ga.description())
    print("=====")
 
    out = []
    for param, fitness in result:
        out.append(param + [fitness])
    df = pd.DataFrame(data=out, columns=['atr_window', 'atrmultiply', 'stoploss', 'takeprofit', 'entry_horizon', 'exit_horizon', 'fitness'])
    df.to_excel('./result/supertrend_invese_best_params_ga_' + symbol + '_' + timeframe + '.xlsx', index=False)

if __name__ == '__main__':
    main('NIKKEI', 'M1')