import os
import sys
sys.path.append('../Libraries/trade')

import shutil
from backtest import DataLoader, TradeBotSim, PositionInfoSim, indicators
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
        

def pickup_trade(trades, tbegin, tend):
    out = []
    for trade in trades:
        if trade.entry_time >= tbegin and trade.entry_time <= tend:
            out.append(trade)
    return out

def plot(data: dict, trades, save, chart_num=0):
    fig, axes = gridFig([5, 1], (20, 10))
    chart1 = CandleChart(fig, axes[0])
    chart1.drawCandle(data[Columns.TIME], data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])
    #name = 'MA' + str(params['MA']['window'])
    #chart.drawLine(data[Columns.TIME], data[name], color='blue')
    chart1.drawLine(data[Columns.TIME], data[Indicators.SUPERTREND_UPPER], color='red', linewidth=2.0)
    chart1.drawLine(data[Columns.TIME], data[Indicators.SUPERTREND_LOWER], color='green', linewidth=2.0)
    
    chart2 = CandleChart(fig, axes[1])
    chart2.drawLine(data[Columns.TIME], data[Indicators.SUPERTREND])
    
    for i, trade in enumerate(trades):
        trade.desc()
        if trade.signal() == Signal.LONG:
            marker = '^'
            color = 'green'
        else:
            marker = 'v'
            color = 'red'
        chart1.drawMarker(trade.entry_time, trade.entry_price, marker, color, markersize=5.0, overlay=i)
        
        if trade.losscutted:
            marker = 'x'
        elif trade.trailing_stopped:
            marker = '*'
        elif trade.time_upped:
            marker = 's'
        else:
            marker = 'o'
        if trade.profit is not None:
            if trade.profit < 0:
                color = 'gray'
        chart1.drawMarker(trade.exit_time, trade.exit_price, marker, color, overlay=i)            
    if save:
        plt.savefig('./charts/fig' + str(chart_num) + '.png')
    else:
        plt.show()
    
                
def plot_days(data, trades, days=7, is_start_monday=True):
    def next_monday(t: datetime):
        t1 = t
        while True:
            if t1.weekday() == 0:
                return t1
            t1 += timedelta(days=1)        
            return t1
    time = data[Columns.TIME]
    if is_start_monday:
        t = next_monday(time[0])
        t = datetime(t.year, t.month, t.day, tzinfo=JST)
    else:
        t = time[0]

    tend = time[-1]
    tend = datetime(tend.year, tend.month, tend.day, tzinfo=JST) + timedelta(days=1)
    count = 1
    while t < tend:
        t1 = t + timedelta(days=days)
        try:
            n, d = Utils.sliceBetween(data, time, t, t1)
            if n < 40:
                t += timedelta(days=days)
                continue
        except:
            t += timedelta(days=days)
            continue
        trds = pickup_trade(trades, t, t1)
        plot(d, trds, True, count)
        count += 1
        t += timedelta(days=days)        
        

def simulate(symbol, timeframe):
    loader = DataLoader()
    n = loader.load_data(symbol, timeframe, range(2020, 2024), range(1, 13))
    technical_param = {'atr_window': 20, 'atr_multiply': 0.8}
    data = loader.data()
    indicators(data, technical_param)
    trade_param =  {'sl':350, 'target_profit': 400, 'trailing_stop': 200, 'volume': 0.1, 'position_max': 5, 'timelimit': 0}
    sim = TradeBotSim(symbol, timeframe, trade_param)
    sim.run(data, 150)
    while True:
        r = sim.update()
        if r == False:
            break
    trades = sim.positions
    (df, profit, num, profit_max, profit_min, win_rate) = PositionInfoSim.summary(trades)
    df['entry_time'] = [str(t) for t in df['entry_time']]
    df['exit_time'] = [str(t) for t in df['exit_time']]
    df.to_excel('./result/trade_summary_' + symbol + '_' + timeframe + '.xlsx')
    print(symbol, timeframe, 'profit', profit, 'drawdown', profit_min, 'num', num, )
    plot_days(data, trades)
    pass        

def test():
    shutil.rmtree('./charts/')
    os.makedirs('./charts', exist_ok=True)
    symbol = 'NIKKEI'
    timeframe = 'M30'
    simulate(symbol, timeframe)
    
if __name__ == '__main__':
    test()