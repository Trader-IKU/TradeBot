# -*- coding: utf-8 -*-
"""
Created on Sun Nov  5 21:44:13 2023

@author: docs9
"""

import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from mt5_trade import Mt5Trade, TimeFrame
from datetime import datetime, timedelta, timezone
import pytz



def download(symbol, save_holder):
    trading = Mt5Trade(symbol)
    for tf in ['TICK', TimeFrame.M1, TimeFrame.M5, TimeFrame.M15, TimeFrame.M30, TimeFrame.H1, TimeFrame.H4, TimeFrame.D1]:
        for year in [2020, 2021, 2022, 2023]:
            for month in range(1, 13):
                t0 = datetime(year, month, 1, tzinfo=timezone.utc)
                t1 = t0 + relativedelta(months=1) - timedelta(seconds=1)
                if tf == 'TICK':
                    rates = trading.get_ticks(t0, t1)
                else:
                    rates = trading.get_rates(tf, t0, t1)
                path = os.path.join(save_holder, symbol, tf)
                os.makedirs(path, exist_ok=True)
                path = os.path.join(path, symbol + '_' + tf + '_' + str(year) + '_' + str(month).zfill(2) + '.csv')
                rates.to_csv(path, index=False)
    
    pass


if __name__ == '__main__':
    download('NSDQ', '../MarketData/Axiory/')

