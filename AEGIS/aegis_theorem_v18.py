#!/data/data/com.termux/files/usr/bin/python

"""
AEGIS‑Theorem v18 – check modulo‑by‑zero on the original tree.
"""

import random
import copy
import math
from typing import List, Tuple, Set

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
        if self.value in ['abs', 'floor', 'sq']:
            return f'{self.value}({repr(self.left)})'
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
        # Unary operators
        if self.value in ['abs', 'floor', 'sq']:
            child = self.left.simplify() if self.left else None
            if child is not None and child.is_terminal():
                if child.value not in ['x','y','z']:
                    val = child.value
                    if self.value == 'abs':
                        return Node(abs(val))
                    elif self.value == 'floor':
                        return Node(math.floor(val))
                    elif self.value == 'sq':
                        return Node(val * val)
            return Node(self.value, child)
        # Binary operators – simplify children first
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
                    elif self.value == '%':
                        if b != 0:
                            return Node(a % b)
                        else:
                            return Node(0)
        # Identity simplifications
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
        elif self.value == '%':
            if right is not None and right.is_terminal() and right.value == 1:
                return Node(0)
            if left is not None and left.is_terminal() and left.value == 0:
                return Node(0)
            if left is not None and right is not None:
                if left.is_terminal() and right.is_terminal():
                    if left.value not in ['x','y','z'] and right.value not in ['x','y','z']:
                        if right.value != 0:
                            return Node(left.value % right.value)
                        else:
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
        if self.value in ['abs', 'floor', 'sq']:
            val = self.left.evaluate_int(x, y, z)
            if self.value == 'abs':
                return abs(val)
            elif self.value == 'floor':
                return math.floor(val)
            elif self.value == 'sq':
                return val * val
        a = self.left.evaluate_int(x, y, z) if self.left else 0
        b = self.right.evaluate_int(x, y, z) if self.right else 0
        if self.value == '+':
            return a + b
        elif self.value == '-':
            return a - b
        elif self.value == '*':
            return a * b
        elif self.value == '%':
            if b == 0:
                return 0
            return a % b
        return 0

class GeneticProgram:
    def __init__(self, pop_size=500, generations=300, max_depth=8):
        self.pop_size = pop_size
        self.generations = generations
        self.max_depth = max_depth
        self.operators = ['+', '-', '*', '%', 'abs', 'floor', 'sq']
        self.terminals = ['x', 'y', 'z']
        self.constants = list(range(-10, 11))
        self.population = []
        self.best_individual = None
        self.best_fitness = float('-inf')

    def seed_valid_identity(self):
        x = Node('x')
        y = Node('y')
        zero = Node('-', x, x.clone())
        return Node('*', zero, y)

    def random_tree(self, depth):
        if depth >= self.max_depth or (depth > 0 and random.random() < 0.3):
            choice = random.choice(self.terminals + self.constants)
            return Node(choice)
        else:
            op = random.choice(self.operators)
            if op in ['abs', 'floor', 'sq']:
                return Node(op, self.random_tree(depth+1), None)
            else:
                return Node(op, self.random_tree(depth+1), self.random_tree(depth+1))

    def contains_mod_zero(self, node):
        """Check if the node contains a modulo operation with a zero right child."""
        if node is None:
            return False
        if node.value == '%' and node.right is not None and node.right.is_terminal() and node.right.value == 0:
            return True
        return self.contains_mod_zero(node.left) or self.contains_mod_zero(node.right)

    def fitness(self, node, data_list):
        # Check for modulo by zero BEFORE simplification
        if self.contains_mod_zero(node):
            return float('-inf')

        simplified = node.simplify()

        # 1. Must contain at least two distinct variables
        def vars_used(n):
            if n.is_terminal():
                return {n.value} if n.value in ['x','y','z'] else set()
            return vars_used(n.left) | vars_used(n.right) if n.right else vars_used(n.left)
        variables = vars_used(simplified)
        if len(variables) < 2:
            return float('-inf')

        # 2. Must not simplify to a constant
        if simplified.is_terminal() and simplified.value not in ['x','y','z']:
            return float('-inf')

        # 3. Must evaluate to zero on ALL training bounds
        for data in data_list:
            for x, y, z in data:
                if simplified.evaluate_int(x, y, z) != 0:
                    return float('-inf')

        # 4. Novelty filter: reject trivial patterns
        rep = repr(simplified)
        if rep in ['0', '1', '-1', '0.0', '1.0', '-1.0']:
            return float('-inf')
        if rep.startswith('(') and ' - ' in rep:
            parts = rep.split(' - ')
            if len(parts) == 2 and parts[0] == parts[1]:
                return float('-inf')
        if '* 0' in rep or '0 *' in rep:
            return float('-inf')

        # 5. Fitness = node_count (maximize)
        return simplified.node_count() + (len(variables) * 2)

    def tournament_select(self, fitnesses, size=5):
        idx = random.sample(range(len(self.population)), size)
        best = max(idx, key=lambda i: fitnesses[i])
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

    def evolve(self, data_list):
        seed = self.seed_valid_identity()
        self.population = [seed] + [self.random_tree(0) for _ in range(self.pop_size-1)]
        self.best_individual = seed.clone()
        self.best_fitness = self.fitness(seed, data_list)

        for gen in range(self.generations):
            fitnesses = [self.fitness(ind, data_list) for ind in self.population]
            min_idx = max(range(len(fitnesses)), key=lambda i: fitnesses[i])
            if fitnesses[min_idx] > self.best_fitness:
                self.best_fitness = fitnesses[min_idx]
                self.best_individual = self.population[min_idx].clone()
                self.best_individual = self.best_individual.simplify()
            if gen % 20 == 0:
                print(f"  Gen {gen}: best fitness = {self.best_fitness:.1f}")
            new_pop = []
            new_pop.append(self.best_individual.clone())
            if len(self.population) >= 2:
                second_idx = max([i for i in range(len(fitnesses)) if i != min_idx], key=lambda i: fitnesses[i])
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

def generate_data(bounds):
    data_list = []
    for b in bounds:
        data = []
        for x in range(-b, b+1):
            for y in range(-b, b+1):
                for z in range(-b, b+1):
                    if x == 0 and y == 0 and z == 0:
                        continue
                    data.append((x, y, z))
        data_list.append(data)
    return data_list

def main():
    print("="*72)
    print("AEGIS‑Theorem v18 – modulo‑by‑zero check on original tree")
    print("="*72)
    bounds = [3, 4, 5]
    data_list = generate_data(bounds)
    total_triples = sum(len(d) for d in data_list)
    print(f"Training data: {total_triples} triples across bounds {bounds}")
    gp = GeneticProgram(pop_size=500, generations=300, max_depth=8)
    best = gp.evolve(data_list)
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
