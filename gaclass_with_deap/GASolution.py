# -*- coding: utf-8 -*-
"""
Created on Wed Dec  7 16:09:12 2022

@author: dcela
"""

import numpy as np
import random
from deap import base, creator, tools
import matplotlib.pyplot as plt


DataType = int
GeneInt: DataType = 1
GeneFloat: DataType = 2
GeneList: DataType = 3

GAType = float
GA_MAXIMIZE: GAType = 1.0
GA_MINIMIZE: GAType = -1.0 

CrossoverType = int
CROSSOVER_ONE_POINT: CrossoverType = 1
CROSSOVER_TWO_POINT: CrossoverType = 2

DEBUG_ENABLE = True


class GASolution:

    # ga_type: GA_MAXIMIZE or GA_MINIMIZE 適合率を最大化もしくは最小化するかを選択
    # gene_space: 遺伝子情報の値の範囲を設定
    # inputs: 必要な情報を入れておく
    # crossover_type: 1点交差　or 2点交差を選択
    # crossover_prob: 交差する確率を設定
    # mutation_prob: 突然変異する確率を設定    
    def __init__(self, 
                         ga_type: GAType, 
                         gene_space: list,
                         inputs: dict,
                         crossover_type: CrossoverType, 
                         crossover_prob: float,
                         mutation_prob: float
                         ):
        
        self.ga_type = ga_type
        self.gene_space = gene_space
        self.crossover_type = crossover_type
        self.crossover_prob = crossover_prob
        self.mutation_prob = mutation_prob
        self.inputs = inputs
        self.params = {}
        self.debug = {}

        #Class 
        creator.create("Fitness", base.Fitness, weights=(ga_type,))
        creator.create("Individual", list, fitness=creator.Fitness)
        
    # params: 実行に必要なパラメータをセット
    def setup(self, params: dict):
        self.params = params
        
        toolbox = base.Toolbox()
        self.toolbox = toolbox
        
        #Method
        toolbox.register('create', self.createGeneticCode, self.gene_space)
        toolbox.register('individual', tools.initIterate, creator.Individual, toolbox.create)
        toolbox.register('population', tools.initRepeat, list, toolbox.individual)
        toolbox.register('evaluate', self.evaluate, inputs=self.inputs, params=self.params)
        if self.crossover_type == CROSSOVER_ONE_POINT:
            toolbox.register('crossover', tools.cxOnePoint)
        elif self.crossover_type == CROSSOVER_TWO_POINT:
            toolbox.register('crossover', tools.cxTwoPoint)
        toolbox.register('mutate', self.mutate, indpb=self.mutation_prob)
        toolbox.register('select', tools.selTournament, tournsize=3)
        
    def description(self):
        s = ''
        s += 'Genetic Code Space: ' + str(self.gene_space) + '\n' 
        if self.crossover_type == CROSSOVER_ONE_POINT:
            s += 'Crossover Type: One Point\n'
        elif self.crossover_type == CROSSOVER_TWO_POINT:
            s += 'Crossover Type: Two Point\n'
        s += 'Crossover Probability: ' + str(self.crossover_prob) + '\n'
        s += 'Mutation Probability: ' + str(self.mutation_prob) + '\n'
        s += 'Parent Selection Method: Tournament'
        return s
    
    def gen_number(self, gene_space):
        typ = gene_space[0]
        if typ == GeneList:
            lis = gene_space[1]
            n = len(lis)
            i = random.randint(0, n - 1)
            return lis[i]
        
        begin = gene_space[1]
        end = gene_space[2]
        step = gene_space[3]
        num = int((end - begin) / step) + 1
        i = random.randint(0, num - 1)
        out = begin + step * i
        if typ == GeneInt:
            return int(out)
        elif typ == GeneFloat:
            return float(out)
        
    # 遺伝子コードの生成
    def createGeneticCode(self, gene_space: list):
        for _ in range(5000000):
            code = self.createCode(gene_space)
            fitness = self.evaluate(code, self.inputs, self.params)
            if fitness[0] > 0:
                return code
        return code
                
    def createCode(self, gene_space):
        n = len(gene_space)
        code = []
        for i in range(n):
            space = gene_space[i]
            value = self.gen_number(space)
            code.append(value)
        return code
    
    #　個体を変異させる
    def mutate(self, individual, indpb):
        for i in range(len(individual)):
            if random.random() < indpb:
                space = self.gene_space[i]
                individual[i] = self.gen_number(space)
        return [individual]
        
    # 個体の評価値を算出する
    def evaluate(self, individual, inputs: dict, params: dict):
        s = np.sum(np.array(individual))
        return [s]
    
    def individualValue(self, individual):
        values = [v for v in individual]
        return values
    
    # Individual class配列から値をとりだす
    def individualsValue(self, individuals):
        result = []
        for individual in individuals:
            values = [v for v in individual]
            values.append(individual.fitness.values[0])
            result.append(values)
        return result    

    # Individual class配列より適合率とその統計値をとりだす
    def pickupFitness(self, individuals):
        fits = [ind.fitness.values[0] for ind in individuals]
        length = len(individuals)
        mean = sum(fits) / length
        sum2 = sum(x * x for x in fits)
        std = abs(sum2 / length - mean ** 2) ** 0.5
        return fits, min(fits), max(fits), mean, std
    
    # 適合率をプロットする
    def plot(self, fitness, fitness_mean, save_path, should_show=True):
        fig = plt.figure(figsize=(10, 5))
        label = 'Max' if self.ga_type == GA_MAXIMIZE else 'Min' 
        plt.plot(range(len(fitness)), fitness, label=label, color='blue')
        plt.plot(range(len(fitness_mean)), fitness_mean, label='Mean', color='green')
        plt.xlabel('generation')
        plt.ylabel('fitness')
        plt.legend() 
        if save_path is not None:
            plt.savefig(save_path, bbox_inches='tight')
        if should_show:
            plt.show()    
            plt.close(fig)
        plt.show()
            
    #　進化ループ
    # num_generation: 進化世代数
    # num_population: 1世代の個体数
    # num_top: 進化した結果で評価の高い順に戻す数
    # should_plot: 評価値のプロットするかどうか
    def run(self, num_generation:int, num_population: int, num_top:int, save_path=None, should_plot:bool=True):
        
        #第1世代の生成と評価
        group = self.toolbox.population(n=num_population)
        fitnesses = list(map(self.toolbox.evaluate, group))
        for ind, fit in zip(group, fitnesses):
            ind.fitness.values = fit

        if DEBUG_ENABLE:
            self.debug['Gen#1'] = self.individualsValue(group) 
                
        fitness_array = []
        fitness_mean = []
        for i in range(2, num_generation + 2):
            print('<世代>', i)
            #子世代を親世代より選択
            offspring = self.toolbox.select(group, len(group))
            offspring = list(map(self.toolbox.clone, offspring))
            
            if DEBUG_ENABLE:
                if i >= 2 and i < 6:
                    self.debug[f'Gen#{i - 1}_offspring'] = self.individualsValue(offspring) 
            
            #交差
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < self.crossover_prob:
                    #print('crossover before', child1, child2)
                    self.toolbox.crossover(child1, child2)
                    #print('crossover after', child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values

            # 変異
            for mutant in offspring:
                if random.random() < self.mutation_prob:
                    #print('mutate before', mutant)
                    self.toolbox.mutate(mutant)
                    #print('mutate after', mutant)
                    del mutant.fitness.values

            # 評価アップデート
            invalids = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = map(self.toolbox.evaluate, invalids)
            for ind, fit in zip(invalids, fitnesses):
                ind.fitness.values = fit

            # 世代の更新
            group[:] = offspring
    
            if DEBUG_ENABLE:
                if i >= 2 and i < 6:
                    self.debug[f'Gen#{i}'] = self.individualsValue(group) 
    
            # 適応度の統計情報の出力
            fits, minv, maxv, mean, std = self.pickupFitness(group)
            fitness_mean.append(mean)
            if self.ga_type == GA_MAXIMIZE:
                fitness_array.append(maxv)
            else:
                fitness_array.append(minv)
            
            #print(f'Generatin #{i} fitness ... min:{minv} max:{maxv} mean:{mean} stdev:{std}')
         
        if should_plot:
            self.plot(fitness_array, fitness_mean, save_path, should_show=should_plot)   

        #適合率の高い順に個体を選出
        top = tools.selBest(group, num_top)
        return self.individualsValue(top)