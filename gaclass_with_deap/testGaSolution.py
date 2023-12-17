# -*- coding: utf-8 -*-
"""
Created on Thu Dec  8 15:05:36 2022

@author: dcela
"""

import random
from GASolution import GASolution, GA_MAXIMIZE, CROSSOVER_ONE_POINT

def test():
    random.seed(1)
    gene_space = [[50, 360], [50, 360], [5, 360]]
    ga = GASolution(GA_MAXIMIZE, gene_space, {}, CROSSOVER_ONE_POINT, 0.3, 0.1)
    result = ga.run(100, 1000, 100, {})
    
    print("=====")
    print(ga.description())
    print("=====")
    print(f"ベスト {result[0][0]}, fitness: {result[0][1]}")

if __name__ == '__main__':
    test()