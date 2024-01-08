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
    fig, axes = makeFig(2, 1, (20, 15))
    chart = CandleChart(fig, axes[0])
    chart.drawCandle(data[Columns.TIME], data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])
    chart.drawLine(data[Columns.TIME], data['MA60'], color='blue')
    chart.drawLine(data[Columns.TIME], data[Indicators.ATR_U], color='green')
    chart.drawLine(data[Columns.TIME], data[Indicators.ATR_L], color='red')
    chart2 = CandleChart(fig, axes[1])
    #chart2.drawCandle(data[Columns.TIME], data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])
    chart2.drawLine(data[Columns.TIME], data['VOLATILITY'], color='blue')
    #chart2.drawLine(data[Columns.TIME], data[Indicators.SUPERTREND_U], color='green')
    #chart2.drawLine(data[Columns.TIME], data[Indicators.SUPERTREND_L], color='red')
    plt.show()
    pass

def test():
    symbol = 'USDJPY'
    timeframe = 'M5'
    params = {'MA':{'window': 60}, 'VOLATILITY':{'window': 50}, 'ATR': {'window': 20, 'multiply':2.0}}
    
    data = load_data(symbol, timeframe, [2024], [1])
    add_indicators(data, params)
    plot(data)
    pass
    
if __name__ == '__main__':
    test()