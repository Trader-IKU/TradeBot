# -*- coding: utf-8 -*-
"""
Created on Sun Nov  5 21:44:13 2023

@author: docs9
"""

from mt5_trade import Trading, TimeFrame
from datetime import datetime, timedelta, timezone
import pytz



def download():
    trading = Trading('DOW')

    tf = TimeFrame(TimeFrame.M1)
    t0 = datetime(2023, 10, 30, tzinfo=timezone.utc)
    t1 = datetime(2023, 10, 31, tzinfo=timezone.utc)
    rates = trading.get_rates(tf, t0, t1)
    rates.to_csv('./dow_m1.csv')
    
    ticks = trading.get_ticks(t0, t1)
    ticks.to_csv('./dow_tick.csv')
    
    pass


if __name__ == '__main__':
    download()

