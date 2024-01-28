import os
import sys
sys.path.append('../Libraries/trade')

import shutil
from backtest_ga import load_data
from mt5_trade import Mt5TradeSim, Columns, JST, UTC
from datetime import datetime, timedelta
from candle_chart import CandleChart, BandPlot, makeFig, gridFig
import matplotlib.pyplot as plt
from technical import *
from backtest_ga import server_time_str_2_datetime
from time_utils import TimeUtils
from utils import Utils
from dateutil import tz
JST = tz.gettz('Asia/Tokyo')
UTC = tz.gettz('utc')  



def plot(symbol, timeframe, date_str, data: dict, count, save=False):
    fig, axes = gridFig([8, 2, 2, 1, 1, 1] , (20, 12))
    title = symbol + '(' + timeframe + ')'
    chart1 = CandleChart(fig, axes[0], title=title, write_time_range=True)
    chart1.drawCandle(data[Columns.TIME], data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])
    chart1.drawLine(data[Columns.TIME], data['MA5'], color='black')
    chart1.drawLine(data[Columns.TIME], data[Indicators.ATR_UPPER], color='blue')
    chart1.drawLine(data[Columns.TIME], data[Indicators.ATR_LOWER], color='red')
    chart1.drawLine(data[Columns.TIME], data[Indicators.SUPERTREND_UPPER], color='blue', linestyle='dotted',linewidth=3.0)
    chart1.drawLine(data[Columns.TIME], data[Indicators.SUPERTREND_LOWER], color='red', linestyle='dotted', linewidth=3.0)
       
    chart2 = CandleChart(fig, axes[1], comment='ADX')
    chart2.drawLine(data[Columns.TIME], data['ADX'], color='red', linewidth=2.0)
    chart2.drawLine(data[Columns.TIME], data['ADX_LONG'], color='blue', linewidth=1.0)
    
    chart3 = CandleChart(fig, axes[2], comment='ATR')
    chart3.drawLine(data[Columns.TIME], data['ATR'], color='red', linewidth=2.0)    
    chart3.drawLine(data[Columns.TIME], data['ATR_LONG'], color='blue', linewidth=1.0)
    
    chart4 = BandPlot(fig, axes[3], comment='Polarity')
    chart4.drawBand(data[Columns.TIME], data[Indicators.POLARITY],colors={UP: 'cyan', DOWN:'red', 0:'white'})
    chart5 = BandPlot(fig, axes[4], comment='ADX+DI')
    chart5.drawBand(data[Columns.TIME], data[Indicators.TREND_ADX_DI],colors={UP: 'cyan', DOWN:'red', 0:'white'})
    chart6 = BandPlot(fig, axes[5], comment='SUPER')
    chart6.drawBand(data[Columns.TIME], data[Indicators.SUPERTREND], colors={UP: 'cyan', DOWN:'red', 0:'white'})
    
    if save:
        plt.savefig('./charts/' + symbol + '_' + timeframe + '_'+ date_str + '_' + str(count) + '.png')
    else:
        plt.show()
    pass

def pickup_trade(trades, tbegin, tend):
    out = []
    for trade in trades:
        if trade.open_time >= tbegin and trade.open_time <= tend:
            out.append(trade)
    return out
    
def plot_charts(symbol, timeframe, data: dict, days=7, is_first_monday=True):
    def next_monday(t: datetime):
        t1 = t
        while True:
            if t1.weekday() == 0:
                return t1
            t1 += timedelta(days=1)           
    time = data[Columns.TIME]
    t = time[0]
    if is_first_monday:
        t = next_monday(time[0])
        t = datetime(t.year, t.month, t.day, tzinfo=JST)
    tend = time[-1]
    count = 1
    while t < tend:
        t1 = t + timedelta(days=days)
        n, d = Utils.sliceBetween(data, time, t, t1)
        if n > 50:
            date_str = str(t.year) + '-' + str(t.month).zfill(2)
            plot(symbol, timeframe, date_str, d, count)
            count += 1
        t += timedelta(days=days)        
        
  
def indicators(data: dict, param):
    atr_window = param['atr_window']
    atr_multiply = param['atr_multiply']
    di_window = param['di_window']
    adx_window = param['adx_window']
    polarity_window = param['polarity_window']
    
    MA(data, Columns.CLOSE, 5)
    ATR(data, atr_window, atr_window * 2, atr_multiply)
    ADX(data, di_window, adx_window, adx_window * 2)
    POLARITY(data, polarity_window)
    TREND_ADX_DI(data, 20)
    SUPERTREND(data)


def simulate(symbol, timeframe):
    year = 2023
    data = load_data(symbol, timeframe, [year], range(1, 13))
    p = {'atr_window': 50, 'atr_multiply': 3.0, 'di_window': 25, 'adx_window': 25, 'polarity_window': 50}
    indicators(data, p)
    plot_charts(symbol, timeframe, data, days=7, is_first_monday=True)
    pass        

def test():
    shutil.rmtree('./charts/')
    os.makedirs('./charts', exist_ok=True)
    symbol = 'NIKKEI'
    timeframe = 'M15'
    simulate(symbol, timeframe)
    
if __name__ == '__main__':
    test()