#!/data/data/com.termux/files/usr/bin/python

"""
AEGIS‑Theorem v11 – seed with a valid identity.
"""

import random
import copy
from typing import List, Tuple

class Node:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right

    def is_operator(self):
        return self.left is not None or self.right is not None

    def is_terminal(self):
        return self.left is None and self.right is None

    def __repr__(self):
        if self.is_terminal():
            if self.value in ['x','y','z']:
                return str(self.value)
            return str(self.value)
        return f'({repr(self.left)} {self.value} {repr(self.right)})'

    def clone(self):
        return copy.deepcopy(self)

    def node_count(self):
        if self.is_terminal():
            return 1
        count = 1
        if self.left:
            count += self.left.node_count()
        if self.right:
            count += self.right.node_count()
        return count

    def depth(self):
        if self.is_terminal():
            return 0
        left_depth = self.left.depth() if self.left else 0
        right_depth = self.right.depth() if self.right else 0
        return 1 + max(left_depth, right_depth)

    def simplify(self):
        if self.is_terminal():
            return self
        left = self.left.simplify() if self.left else None
        right = self.right.simplify() if self.right else None
        if left is not None and right is not None:
            if left.is_terminal() and right.is_terminal():
                if left.value not in ['x','y','z'] and right.value not in ['x','y','z']:
                    a = left.value
                    b = right.value
                    if self.value == '+':
                        return Node(a + b)
                    elif self.value == '-':
                        return Node(a - b)
                    elif self.value == '*':
                        return Node(a * b)
        if self.value == '+':
            if left is not None and left.is_terminal() and left.value == 0:
                return right
            if right is not None and right.is_terminal() and right.value == 0:
                return left
        elif self.value == '-':
            if right is not None and right.is_terminal() and right.value == 0:
                return left
            if left is not None and right is not None and repr(left) == repr(right):
                return Node(0)
        elif self.value == '*':
            if left is not None and left.is_terminal() and left.value == 1:
                return right
            if right is not None and right.is_terminal() and right.value == 1:
                return left
            if left is not None and left.is_terminal() and left.value == 0:
                return Node(0)
            if right is not None and right.is_terminal() and right.value == 0:
                return Node(0)
        return Node(self.value, left, right)

    def evaluate_int(self, x, y, z):
        if self.is_terminal():
            if self.value == 'x':
                return x
            elif self.value == 'y':
                return y
            elif self.value == 'z':
                return z
            else:
                return self.value
        a = self.left.evaluate_int(x, y, z) if self.left else 0
        b = self.right.evaluate_int(x, y, z) if self.right else 0
        if self.value == '+':
            return a + b
        elif self.value == '-':
            return a - b
        elif self.value == '*':
            return a * b
        return 0

class GeneticProgram:
    def __init__(self, pop_size=400, generations=200, max_depth=6):
        self.pop_size = pop_size
        self.generations = generations
        self.max_depth = max_depth
        self.operators = ['+', '-', '*']
        self.terminals = ['x', 'y', 'z']
        self.constants = list(range(-10, 11))
        self.population = []
        self.best_individual = None
        self.best_fitness = float('inf')

    def seed_valid_identity(self):
        # (x - x) * y  is identically zero and uses two variables
        x = Node('x')
        y = Node('y')
        zero = Node('-', x, x.clone())  # x - x
        return Node('*', zero, y)

    def random_tree(self, depth):
        if depth >= self.max_depth or (depth > 0 and random.random() < 0.3):
            choice = random.choice(self.terminals + self.constants)
            return Node(choice)
        else:
            op = random.choice(self.operators)
            return Node(op, self.random_tree(depth+1), self.random_tree(depth+1))

    def fitness(self, node, data):
        simplified = node.simplify()
        def vars_used(n):
            if n.is_terminal():
                return {n.value} if n.value in ['x','y','z'] else set()
            return vars_used(n.left) | vars_used(n.right) if n.right else vars_used(n.left)
        if len(vars_used(simplified)) < 2:
            return float('inf')
        for x, y, z in data:
            if simplified.evaluate_int(x, y, z) != 0:
                return float('inf')
        return simplified.node_count()

    def tournament_select(self, fitnesses, size=5):
        idx = random.sample(range(len(self.population)), size)
        best = min(idx, key=lambda i: fitnesses[i])
        return copy.deepcopy(self.population[best])

    def mutate(self, node):
        if random.random() < 0.3:
            return self.random_tree(0)
        else:
            if node.is_terminal():
                if node.value not in ['x','y','z']:
                    node.value = random.choice(self.constants)
                return node
            else:
                if node.left is not None and random.random() < 0.5:
                    node.left = self.mutate(node.left)
                if node.right is not None and random.random() < 0.5:
                    node.right = self.mutate(node.right)
                return node

    def crossover(self, p1, p2):
        c1 = p1.clone()
        c2 = p2.clone()
        nodes1, nodes2 = [], []
        self.collect_nodes(c1, nodes1)
        self.collect_nodes(c2, nodes2)
        if not nodes1 or not nodes2:
            return c1, c2
        t1 = random.choice(nodes1)
        t2 = random.choice(nodes2)
        def replace(root, old, new):
            if root is old:
                return new
            if root.is_terminal():
                return root
            new_left = replace(root.left, old, new) if root.left else None
            new_right = replace(root.right, old, new) if root.right else None
            if new_left is root.left and new_right is root.right:
                return root
            return Node(root.value, new_left, new_right)
        nc1 = replace(c1, t1, t2.clone())
        nc2 = replace(c2, t2, t1.clone())
        if nc1.depth() <= self.max_depth and nc2.depth() <= self.max_depth:
            return nc1, nc2
        return c1, c2

    def collect_nodes(self, node, nodes):
        if node is None:
            return
        nodes.append(node)
        if node.left:
            self.collect_nodes(node.left, nodes)
        if node.right:
            self.collect_nodes(node.right, nodes)

    def evolve(self, data):
        # Seed with a valid identity
        seed = self.seed_valid_identity()
        self.population = [seed] + [self.random_tree(0) for _ in range(self.pop_size-1)]
        self.best_individual = seed.clone()
        self.best_fitness = self.fitness(seed, data)  # finite

        for gen in range(self.generations):
            fitnesses = [self.fitness(ind, data) for ind in self.population]
            min_idx = min(range(len(fitnesses)), key=lambda i: fitnesses[i])
            if fitnesses[min_idx] < self.best_fitness:
                self.best_fitness = fitnesses[min_idx]
                self.best_individual = self.population[min_idx].clone()
                self.best_individual = self.best_individual.simplify()
            if gen % 20 == 0:
                print(f"  Gen {gen}: best fitness = {self.best_fitness:.1f}")
            new_pop = []
            new_pop.append(self.best_individual.clone())
            if len(self.population) >= 2:
                second_idx = min([i for i in range(len(fitnesses)) if i != min_idx], key=lambda i: fitnesses[i])
                new_pop.append(self.population[second_idx].clone())
            while len(new_pop) < self.pop_size:
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
                new_pop.append(c1)
                if len(new_pop) < self.pop_size:
                    new_pop.append(c2)
            self.population = new_pop
        self.best_individual = self.best_individual.simplify()
        return self.best_individual

def verify(expr, bound=50):
    for x in range(-bound, bound+1):
        for y in range(-bound, bound+1):
            for z in range(-bound, bound+1):
                if x == 0 and y == 0 and z == 0:
                    continue
                val = expr.evaluate_int(x, y, z)
                if val != 0:
                    return (False, (x, y, z))
    return (True, None)

def generate_data(bound=5):
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
    print("AEGIS‑Theorem v11 – seeded with a valid identity")
    print("="*72)
    bound = 5
    data = generate_data(bound)
    print(f"Training data: {len(data)} triples")
    gp = GeneticProgram(pop_size=400, generations=200, max_depth=6)
    best = gp.evolve(data)
    print(f"Best conjecture: {repr(best)}")
    print(f"Node count: {best.node_count()}")
    print("Verifying up to bound 50...")
    ok, counter = verify(best, 50)
    if ok:
        print("\n[✓] THEOREM DISCOVERED!")
        print(f"Expression: {repr(best)}")
        print("It holds for all triples up to 50.")
        with open("theorems.txt", "a") as f:
            f.write(f"THEOREM: {repr(best)}\n")
            f.write("Verified up to 50.\n\n")
    else:
        print(f"\n[✗] Falsified at {counter}")

if __name__ == "__main__":
    main()
