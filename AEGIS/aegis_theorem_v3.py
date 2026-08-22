#!/data/data/com.termux/files/usr/bin/python

"""
AEGIS‑Theorem v3 – integer identity search with basic arithmetic only.
Operators: +, -, *, / (no trig or transcendental).
Complexity penalty to avoid trivial identities.
"""

import math
import random
import copy
from typing import List, Optional, Tuple

class Node:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right
        self.arity = 0
        if left is not None:
            self.arity += 1
        if right is not None:
            self.arity += 1

    def is_operator(self):
        return self.arity > 0

    def is_terminal(self):
        return self.arity == 0

    def __repr__(self):
        if self.is_terminal():
            if self.value in ['x', 'y', 'z']:
                return str(self.value)
            else:
                return f'{float(self.value):.4f}'
        elif self.arity == 1:
            return f'{self.value}({repr(self.left)})'
        else:
            return f'({repr(self.left)} {self.value} {repr(self.right)})'

    def depth(self):
        if self.is_terminal():
            return 0
        left_depth = self.left.depth() if self.left else 0
        right_depth = self.right.depth() if self.right else 0
        return 1 + max(left_depth, right_depth)

    def node_count(self):
        if self.is_terminal():
            return 1
        return 1 + (self.left.node_count() if self.left else 0) + (self.right.node_count() if self.right else 0)

    def clone(self):
        return copy.deepcopy(self)

    def simplify(self):
        if self.is_terminal():
            return self
        left = self.left.simplify() if self.left else None
        right = self.right.simplify() if self.right else None
        if self.value == '+':
            if left is not None and left.is_terminal() and left.value == 0:
                return right
            if right is not None and right.is_terminal() and right.value == 0:
                return left
        elif self.value == '*':
            if left is not None and left.is_terminal() and left.value == 1:
                return right
            if right is not None and right.is_terminal() and right.value == 1:
                return left
            if left is not None and left.is_terminal() and left.value == 0:
                return Node(0.0)
            if right is not None and right.is_terminal() and right.value == 0:
                return Node(0.0)
        elif self.value == '/':
            if right is not None and right.is_terminal() and right.value == 1:
                return left
            if left is not None and right is not None and repr(left) == repr(right):
                return Node(1.0)
        return Node(self.value, left, right)

    def evaluate(self, x, y, z):
        if self.is_terminal():
            if self.value == 'x':
                return x
            elif self.value == 'y':
                return y
            elif self.value == 'z':
                return z
            else:
                return float(self.value)
        if self.value == '+':
            return self.left.evaluate(x, y, z) + self.right.evaluate(x, y, z)
        if self.value == '-':
            if self.right is None:
                return -self.left.evaluate(x, y, z)
            return self.left.evaluate(x, y, z) - self.right.evaluate(x, y, z)
        if self.value == '*':
            return self.left.evaluate(x, y, z) * self.right.evaluate(x, y, z)
        if self.value == '/':
            denom = self.right.evaluate(x, y, z)
            if abs(denom) < 1e-12:
                return float('inf')
            return self.left.evaluate(x, y, z) / denom
        raise ValueError(f"Unknown operator: {self.value}")

# ============================================================
# GENETIC PROGRAMMING
# ============================================================

class GeneticProgram:
    def __init__(self, population_size=300, generations=150, max_depth=5):
        self.population_size = population_size
        self.generations = generations
        self.max_depth = max_depth
        self.operators = ['+', '-', '*', '/']
        self.terminals = ['x', 'y', 'z']
        self.population = []
        self.best_individual = None
        self.best_fitness = float('inf')

    def random_tree(self, depth):
        if depth >= self.max_depth or (depth > 0 and random.random() < 0.3):
            term = random.choice(self.terminals + [random.uniform(-5, 5)])
            if isinstance(term, float):
                return Node(term)
            else:
                return Node(term)
        else:
            op = random.choice(self.operators)
            return Node(op, self.random_tree(depth+1), self.random_tree(depth+1))

    def fitness(self, node, data):
        total = 0.0
        for x, y, z in data:
            val = node.evaluate(x, y, z)
            if math.isinf(val) or math.isnan(val):
                return float('inf')
            total += abs(val)
        error = total / len(data)

        nodes = node.node_count()
        # Penalize trivial expressions
        if nodes <= 3:
            penalty = 10.0
        elif nodes <= 5:
            penalty = 2.0
        elif nodes <= 15:
            penalty = 0.0
        else:
            penalty = 0.05 * (nodes - 15)
        return error + penalty

    def tournament_select(self, fitnesses, tournament_size=5):
        idx = random.sample(range(len(self.population)), tournament_size)
        best_idx = min(idx, key=lambda i: fitnesses[i])
        return copy.deepcopy(self.population[best_idx])

    def mutate(self, node):
        if random.random() < 0.3:
            return self.random_tree(0)
        else:
            if node.is_terminal():
                if node.value not in ['x', 'y', 'z']:
                    node.value = random.uniform(-5, 5)
                return node
            else:
                if node.left is not None and random.random() < 0.5:
                    node.left = self.mutate(node.left)
                if node.right is not None and random.random() < 0.5:
                    node.right = self.mutate(node.right)
                return node

    def crossover(self, parent1, parent2):
        child1 = parent1.clone()
        child2 = parent2.clone()
        nodes1, nodes2 = [], []
        self.collect_nodes(child1, nodes1)
        self.collect_nodes(child2, nodes2)
        if not nodes1 or not nodes2:
            return child1, child2
        target1 = random.choice(nodes1)
        target2 = random.choice(nodes2)
        def replace_subtree(root, old, new):
            if root is old:
                return new
            if root.is_terminal():
                return root
            new_left = replace_subtree(root.left, old, new) if root.left else None
            new_right = replace_subtree(root.right, old, new) if root.right else None
            if new_left is root.left and new_right is root.right:
                return root
            return Node(root.value, new_left, new_right)
        new_child1 = replace_subtree(child1, target1, target2.clone())
        new_child2 = replace_subtree(child2, target2, target1.clone())
        if new_child1.depth() <= self.max_depth and new_child2.depth() <= self.max_depth:
            return new_child1, new_child2
        return child1, child2

    def collect_nodes(self, node, nodes):
        if node is None:
            return
        nodes.append(node)
        if node.left:
            self.collect_nodes(node.left, nodes)
        if node.right:
            self.collect_nodes(node.right, nodes)

    def evolve(self, data):
        self.population = [self.random_tree(0) for _ in range(self.population_size)]
        self.best_individual = None
        self.best_fitness = float('inf')

        for gen in range(self.generations):
            fitnesses = [self.fitness(ind, data) for ind in self.population]
            min_idx = min(range(len(fitnesses)), key=lambda i: fitnesses[i])
            if fitnesses[min_idx] < self.best_fitness:
                self.best_fitness = fitnesses[min_idx]
                self.best_individual = self.population[min_idx].clone()
                self.best_individual = self.best_individual.simplify()

            if gen % 20 == 0:
                print(f"  Gen {gen}: best fitness = {self.best_fitness:.6f}")

            new_population = []
            new_population.append(self.best_individual.clone())
            if len(self.population) >= 2:
                second_idx = min([i for i in range(len(fitnesses)) if i != min_idx], key=lambda i: fitnesses[i])
                new_population.append(self.population[second_idx].clone())
            while len(new_population) < self.population_size:
                p1 = self.tournament_select(fitnesses)
                p2 = self.tournament_select(fitnesses)
                if random.random() < 0.7:
                    c1, c2 = self.crossover(p1, p2)
                else:
                    c1, c2 = p1.clone(), p2.clone()
                if random.random() < 0.15:
                    c1 = self.mutate(c1)
                if random.random() < 0.15:
                    c2 = self.mutate(c2)
                new_population.append(c1)
                if len(new_population) < self.population_size:
                    new_population.append(c2)
            self.population = new_population

        self.best_individual = self.best_individual.simplify()
        self.best_fitness = self.fitness(self.best_individual, data)
        return self.best_individual

# ============================================================
# VERIFIER
# ============================================================

def verify_conjecture(expr, bound=50):
    eps = 1e-6
    for x in range(-bound, bound+1):
        for y in range(-bound, bound+1):
            for z in range(-bound, bound+1):
                if x == 0 and y == 0 and z == 0:
                    continue
                try:
                    val = expr.evaluate(x, y, z)
                except:
                    return (False, (x, y, z))
                if abs(val) > eps:
                    return (False, (x, y, z))
    return (True, None)

def generate_training_data(bound=3):
    data = []
    for x in range(-bound, bound+1):
        for y in range(-bound, bound+1):
            for z in range(-bound, bound+1):
                if x == 0 and y == 0 and z == 0:
                    continue
                data.append((x, y, z))
    return data

def main():
    print("="*72)
    print("AEGIS‑Theorem v3 – integer identities (basic arithmetic)")
    print("="*72)

    train_bound = 3
    print(f"\n[1] Generating training data (|x|,|y|,|z| ≤ {train_bound})...")
    data = generate_training_data(train_bound)
    print(f"    {len(data)} triples.")

    print("\n[2] Running genetic programming...")
    gp = GeneticProgram(population_size=300, generations=150, max_depth=6)
    best_expr = gp.evolve(data)

    print(f"\n[3] Best conjecture: {repr(best_expr)}")
    print(f"    Fitness: {gp.best_fitness:.6f}")
    print(f"    Node count: {best_expr.node_count()}")

    verify_bound = 50
    print(f"\n[4] Verifying for all triples up to bound {verify_bound}...")
    holds, counter = verify_conjecture(best_expr, verify_bound)

    if holds:
        print("\n[✓] THEOREM DISCOVERED!")
        print(f"    Expression: {repr(best_expr)}")
        print(f"    Verified up to {verify_bound}.")
        with open("theorems.txt", "a") as f:
            f.write(f"THEOREM: {repr(best_expr)}\n")
            f.write(f"Verified up to bound {verify_bound}\n\n")
    else:
        print(f"\n[✗] Falsified at {counter}")

    print("\n[5] Done.")

if __name__ == "__main__":
    main()
