import os
import sys
sys.path.append('../Libraries/trade')

from backtest_ga import load_data
from mt5_trade import Mt5TradeSim, Columns, JST, UTC
from datetime import datetime, timedelta
from candle_chart import CandleChart, makeFig
import matplotlib.pyplot as plt
from technical import add_indicators, Indicators
from backtest_ga import server_time_str_2_datetime


def plot(data: dict):
    fig, ax = makeFig(1, 1, (20, 15))
    chart = CandleChart(fig, ax)
    chart.drawCandle(data[Columns.TIME], data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])
    chart.drawLine(data[Columns.TIME], data['MA60'], color='blue')
    chart.drawLine(data[Columns.TIME], data[Indicators.ATR_U], color='green')
    chart.drawLine(data[Columns.TIME], data[Indicators.ATR_L], color='red')
    ax2 = ax.twinx()
    chart2 = CandleChart(fig, ax2)
    chart2.drawLine(data[Columns.TIME], data['VOLATILITY'], color='orange', linewidth=3.0)
    plt.show()
    pass

def test():
    symbol = 'USDJPY'
    timeframe = 'M15'
    params = {'MA':{'window': 60}, 'VOLATILITY':{'window': 50}, 'ATR': {'window': 20, 'multiply':2.0}}
    
    data = load_data(symbol, timeframe, [2024], [1])
    add_indicators(data, params)
    plot(data)
    pass
    
if __name__ == '__main__':
    test()