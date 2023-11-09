from data_loader import DataLoader
from mt5_trade import Mt5TradeSim, JST, UTC
from datetime import datetime, timedelta





def test():
    files = {'M1': './dow_m1.csv',
             'TICK': './dow_tick.csv'}
    server = Mt5TradeSim('DOW', files)
    loader = DataLoader('DOW', files.keys(), server)
    t = datetime(2023, 10, 30, 20, tzinfo=JST)
    loader.run(t, timedelta(hours=8), timedelta(seconds=10))
    for _ in range(10):
        loader.next()

    
if __name__ == '__main__':
    test()