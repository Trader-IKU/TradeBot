import os
import sys
sys.path.append('../Libraries/trade')

from data_loader import DataLoader
from mt5_trade import Mt5TradeSim, Columns, JST, UTC
from datetime import datetime, timedelta
from candle_chart import CandleChart, makeFig
from technical import indicators, Indicators


def analyze(data: dict):
    indicators(data)
    fig, ax = makeFig(1, 1, (20, 15))
    chart = CandleChart(fig, ax)
    chart.drawCandle(data[Columns.TIME], data[Columns.OPEN], data[Columns.HIGH], data[Columns.LOW], data[Columns.CLOSE])
    chart.drawLine(data[Columns.TIME], data['MA9'], color='blue')
    chart.drawLine(data[Columns.TIME], data[Indicators.ATR_U], color='green')
    chart.drawLine(data[Columns.TIME], data[Indicators.ATR_D], color='red')


def test():
    files = {'M1': './dow_m1.csv',
             'TICK': './dow_tick.csv'}
    server = Mt5TradeSim('DOW', files)
    loader = DataLoader('DOW', files.keys(), server)
    t = datetime(2023, 10, 30, 20, tzinfo=JST)
    loader.run(t, timedelta(hours=8), timedelta(seconds=10))
    data = loader.buffers['M1'].data
    analyze(data)
    pass
    
if __name__ == '__main__':
    test()