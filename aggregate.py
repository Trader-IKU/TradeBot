import pandas as pd
import os
import glob


def file_list(dir_path, keywords, extension='*.xlsx'):
    files = glob.glob(os.path.join(dir_path, extension))
    if len(keywords) == 0:
        return files
    l = []
    for file in files:
        found = True
        for keyword in keywords:
            if file.find(keyword) < 0:
                found = False
                break
        if found:
            l.append(file)
    return l

def ref_price(symbol):
    path = '../MarketData/Axiory/' + symbol +  '/D1/' + symbol + '_D1_2020_01.csv'
    df = pd.read_csv(path)
    p = df['open'][0]
    return p

def unite(strategy, symbol):
    symbol = symbol.upper()
    dir = os.path.join('./result', strategy)
    if symbol.strip() == '':
        files = file_list(dir, [])
    else:
        files = file_list(dir, [symbol])
    dfs = []
    for path in files:
        df = pd.read_excel(path)
        dfs.append(df)
    if len(dfs) == 0:
        return None
    df = pd.concat(dfs)
    
    price = ref_price(symbol)
    df['fitness_percent'] = df['fitness'] / price * 100
    df = df.sort_values('fitness_percent', ascending=False)
    return df
    
def main(strategy):
    fx =  ['USDJPY', 'EURJPY', 'EURUSD', 'GBPJPY']
    stock  = ['NIKKEI', 'DOW', 'NSDQ', 'HK50']
    como =  ['XAUUSD', 'CL']
    symbols = fx + stock + como
    dir = os.path.join('./report', strategy)
    os.makedirs(dir, exist_ok=True)
    dfs = []
    for symbol in symbols:
        df = unite(strategy, symbol)
        if df is None:
            continue
        path = os.path.join(dir, symbol + '.xlsx')
        df.to_excel(path, index=False)
        dfs.append(df)
    df = pd.concat(dfs)
    df = df.sort_values('fitness_percent', ascending=False)
    df.to_excel('./report/' + strategy + '.xlsx', index=False)

if __name__ == '__main__':
    main('TrailATR')
    