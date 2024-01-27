import os
import sys
sys.path.append('../Libraries/trade')

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



def plot(data: dict, count):
    fig, axes = gridFig([8, 2, 2, 1, 1] , (20, 12))
    chart1 = CandleChart(fig, axes[0])
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
    
    chart4 = BandPlot(fig, axes[3], comment='ADX+DI')
    chart4.drawBand(data[Columns.TIME], data[Indicators.TREND_ADX_DI],colors={UP: 'cyan', DOWN:'red', 0:'white'})
    chart5 = BandPlot(fig, axes[4], comment='SUPER')
    chart5.drawBand(data[Columns.TIME], data[Indicators.SUPERTREND], colors={UP: 'cyan', DOWN:'red', 0:'white'})
    
    plt.savefig('./charts/fig_' + str(count) + '.png')
    pass

def pickup_trade(trades, tbegin, tend):
    out = []
    for trade in trades:
        if trade.open_time >= tbegin and trade.open_time <= tend:
            out.append(trade)
    return out

        
def plot_charts(data: dict, days=7):
    def next_monday(t: datetime):
        t1 = t
        while True:
            if t1.weekday() == 0:
                return t1
            t1 += timedelta(days=1)           
    time = data[Columns.TIME]
    t = next_monday(time[0])
    t = datetime(t.year, t.month, t.day, tzinfo=JST)
    tend = time[-1]
    count = 1
    while t < tend:
        t1 = t + timedelta(days=days)
        n, d = Utils.sliceBetween(data, time, t, t1)
        if n > 50:
            plot(d, count)
            count += 1
        t += timedelta(days=days)        
        

        
def test():
    os.makedirs('./charts', exist_ok=True)
    symbol = 'NIKKEI'
    timeframe = 'H1'
    params = {'MA':{'window': 60}, 'VOLATILITY':{'window': 50}, 'ATR': {'window': 20, 'multiply':2.0}}
    
    data = load_data(symbol, timeframe, [2024], [1])
    MA(data, Columns.CLOSE, 5)
    ATR(data, 15, 100, 2.0)
    ADX(data, 15, 15, 100)

    TREND_ADX_DI(data, 0.25)
    SUPERTREND(data)
    plot_charts(data, days=7)
    pass
    
if __name__ == '__main__':
    test()