import numpy as np 
import math
import statistics as stat

def nans(length):
    return [np.nan for _ in range(length)]

def full(value, length):
    return [value for _ in range(length)]

def moving_average(vector, out, begin, window):
    n = len(vector)
    for j in range(begin, n):
        i = j - window + 1
        if i < 0:
            i = 0
        d = vector[i : j + 1]
        out[j] = stat.mean(d)
        
def test():
    sig = [1, 2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    ma = full(-1, len(sig))
    
    moving_average(sig, ma, 2, 5)
    print(ma)
    
if __name__ == '__main__':
    test()
    

