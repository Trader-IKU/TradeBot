import os
import sys
sys.path.append('../Libraries/trade')

import shutil
from backtest import DataLoader, PositionInfoSim
from backtest_trail_atr import indicators, TradeBotSimTrailATR
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
    
    
    

def pickup_trade(trades, tbegin, tend):
    out = []
    for trade in trades:
        if trade.open_time >= tbegin and trade.open_time <= tend:
            out.append(trade)
        elif trade.exit_time >= tbegin and trade.exit_time <= tend:
            out.append(trade)
    return out
    
  
        

def pickup_trade(trades, tbegin, tend):
    out = []
    for trade in trades:
        if trade.entry_time >= tbegin and trade.entry_time <= tend:
            out.append(trade)
    return out

def plot(symbol, timeframe, data: dict, trades, chart_num=0):
    fig, axes = gridFig([2, 1], (10, 5))
    time = data[Columns.JST]
    title = symbol + '(' + timeframe + ')  ' + str(time[0]) + '...' + str(time[-1]) 
    chart1 = CandleChart(fig, axes[0], title=title, date_format=CandleChart.DATE_FORMAT_DATE_TIME)
    chart1.drawCandle(time, data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])
    #name = 'MA' + str(params['MA']['window'])
    #chart.drawLine(time, data[name], color='blue')
    chart1.drawLine(time, data[Indicators.ATR_TRAIL_UP], color='cyan', linewidth=2.0)
    chart1.drawLine(time, data[Indicators.ATR_TRAIL_DOWN], color='red', linewidth=2.0)
    chart2 = CandleChart(fig, axes[1], title = title, write_time_range=True, date_format=CandleChart.DATE_FORMAT_DATE_TIME)
    chart2.drawLine(time, data[Indicators.ADX])
    chart2.ylimit([0, 100])
    
    profits = []
    for i, trade in enumerate(trades):
        trade.desc()
        if trade.profit is not None:
            profits.append(trade.profit)
        if trade.signal() == Signal.LONG:
            marker = '^'
            color = 'green'
        else:
            marker = 'v'
            color = 'red'
        chart1.drawMarker(trade.entry_time, trade.entry_price, marker, color, markersize=20.0, overlay=i, overlaycolor='white', overlaysize=15.0)
        
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
            else:
                color = 'blue'
        
        offset = 100 + (i % 10) * 20
        if i % 2 == 0:
            offset *= -1
        if trade.exit_price is not None:
            chart1.drawMarker(trade.exit_time, trade.exit_price, marker, 'gray', markersize=20.0)            
            chart1.drawMarker(trade.exit_time, trade.exit_price + offset, '$' + str(i) + '$', color, markersize=15.0)            
        s = '  Profit:' + str(sum(profits)) +  '   '  + str(profits)
        chart1.comment = s
        chart1.drawComments(True)
    plt.savefig('./chart/analyze/' + 'fig'  + str(chart_num) + '_' + symbol + '_' + timeframe + '.png')

      
        

def simulate(symbol, timeframe):
    strategy = 'TrailATR'
    loader = DataLoader()
    n, data = loader.load_data(symbol, timeframe, 2022, 1, 2024, 2)
    technical_param = {'atr_window': 20, 'atr_multiply': 2.7, 'peak_hold_term': 10}
    indicators(data, technical_param)
    trade_param =  {'sl':500, 'target_profit': 0, 'trailing_stop': 0, 'volume': 0.1, 'position_max': 1, 'timelimit': 0}
    sim = TradeBotSimTrailATR(symbol, timeframe, trade_param)
    sim.run(data, 150)
    count = 0
    while True:
        r = sim.update()
        if r == False:
            break
        print( count, '/', n)
        count += 1
    trades = sim.positions
    (df, acc, statics) = PositionInfoSim.summary(trades)
    df['entry_time'] = [str(t) for t in df['entry_time']]
    df['exit_time'] = [str(t) for t in df['exit_time']]
    df.to_excel('./report/trade_summary_' + strategy + '_' + symbol + '_' + timeframe + '.xlsx')
    print('#' + str(count), symbol, timeframe, 'profit', statics['sum'], 'drawdown', statics['drawdown'], 'num', statics['num'], 'win_rate', statics['win_rate'])    
    fig, ax = makeFig(1, 1, (10, 4))
    title =  'profit_sum: ' + str(statics['sum']) + ' drawdown: ' + str(statics['drawdown'])
    n, data = loader.load_data(symbol, 'D1', 2022, 1, 2024, 2)
    chart1 = CandleChart(fig, ax, title=title)
    #chart1.drawCandle(data[Columns.TIME], data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])
    chart1.drawLine(data[Columns.TIME], data[Columns.CLOSE], color='blue')
    ax2 = ax.twinx()
    chart2 = CandleChart(fig, ax2)
    chart2.drawLine(acc[0], acc[1], color='red', linewidth=1.0)
    plt.show()
    pass        

def test():
    loader = DataLoader()
    n, data = loader.load_data('NIKKEI', 'D1', 2022, 1, 2024, 2)
    pass
    
def analyze():
    symbol = 'NIKKEI'
    timeframe = 'H1'
    simulate(symbol, timeframe)
    
    
def technical_chart(symbol, timeframe):
    loader = DataLoader()
    n, data = loader.load_data(symbol, timeframe, 2018, 1, 2018, 2)
    if n < 100:
        return
    ATR_TRAIL(data, 5, 2.5, 10)
    ADX(data, 14, 14, None)

    time = data[Columns.JST]
    t = time[0]
    t = TimeUtils.pyTime(t.year, t.month, t.day, 22, 0, 0, JST)
    tend = time[-1]
    count = 1
    while t < tend:
        t1 = t + timedelta(hours=3)
        try:
            n, d = Utils.sliceBetween(data, time, t, t1)
            if n < 40:
                t += timedelta(days=1)
                continue
        except:
            t += timedelta(days=1)
            continue
        plot(symbol, timeframe, d, [], count)
        count += 1
        t += timedelta(days=1)        
    

    
    
if __name__ == '__main__':
    try:
        shutil.rmtree('./chart/analyze')
    except:
        pass
    os.makedirs('./chart/analyze', exist_ok=True)
    technical_chart('DOW', 'M1')
    #analyze()