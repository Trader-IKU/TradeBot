# -*- coding: utf-8 -*-
"""
Created on Sun Nov  5 21:44:13 2023

@author: docs9
"""

from mt5_trade import Trading, TimeFrame
from datetime import datetime, timedelta, timezone
import pytz



def download():
    trading = Trading('USDJPY')

    tf = TimeFrame(TimeFrame.M1)
    t0 = datetime(2023, 10, 1, tzinfo=timezone.utc)
    t1 = datetime(2023, 11, 1, tzinfo=timezone.utc)
    rates = trading.get_rates(tf, t0, t1)
    
    pass


if __name__ == '__main__':
    download()

