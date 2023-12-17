# -*- coding: utf-8 -*-
"""
Created on Thu Dec  8 15:05:36 2022

@author: dcela
"""

import random
from GASolution import GASolution, GA_MAXIMIZE, CROSSOVER_ONE_POINT, GeneInt, GeneFloat

def test():
    random.seed(1)
    gene_space = [[GeneInt, 0, 2, 1], [GeneInt, 5, 103, 5], [GeneFloat, 5, 10, 1.0], [GeneFloat, 50, 300, 50]]
    ga = GASolution(GA_MAXIMIZE, gene_space, {}, CROSSOVER_ONE_POINT, 0.3, 0.1)
    
    '''
    nums = []
    for i in range(1000):
        n = ga.gen_number([GeneInt, 5, 103, 5])
        nums.append(n)
    print('Min', min(nums), 'Max', max(nums))
    '''
    
    ga.setup({})
    result = ga.run(100, 1000, 100)
    
    print("=====")
    print(ga.description())
    print("=====")
    print(f"ベスト {result[0][0]}, fitness: {result[0][1]}")

if __name__ == '__main__':
    test()