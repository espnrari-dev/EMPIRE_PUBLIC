#!/data/data/com.termux/files/usr/bin/python

"""
AEGIS Discovery Engine v4 – Genetic Programming with Constant Optimization

This engine searches for symbolic expressions using genetic programming,
but crucially, it refines numeric constants using local optimization
after each generation. This allows it to converge on exact values
like 0.35 or 0.5.

Operators: +, -, *, /, x, constants
Population: 200, Generations: 100
Validation: rate, reconstruction, prediction gates
Promotion: only if all three gates pass
"""

import math
import random
import copy
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple, Callable

# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class Observation:
    x: float
    y: float

# ============================================================
# NODE REPRESENTATION
# ============================================================

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
            if self.value == 'x':
                return 'x'
            else:
                return f'{self.value:.4f}'
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

    def collect_constants(self):
        """Return a list of all constant nodes in the tree."""
        if self.is_terminal():
            if self.value != 'x':
                return [self]
            return []
        result = []
        if self.left:
            result.extend(self.left.collect_constants())
        if self.right:
            result.extend(self.right.collect_constants())
        return result

    def clone(self):
        return copy.deepcopy(self)

# ============================================================
# EVALUATION (with overflow protection)
# ============================================================

def evaluate_node(node, x):
    """Evaluate expression tree at x with overflow protection."""
    if node.is_terminal():
        if node.value == 'x':
            return x
        else:
            return float(node.value)
    elif node.value == '+':
        return evaluate_node(node.left, x) + evaluate_node(node.right, x)
    elif node.value == '-':
        # Handle both binary subtraction and unary negation
        if node.right is None:
            return -evaluate_node(node.left, x)
        return evaluate_node(node.left, x) - evaluate_node(node.right, x)
    elif node.value == '*':
        return evaluate_node(node.left, x) * evaluate_node(node.right, x)
    elif node.value == '/':
        denom = evaluate_node(node.right, x)
        if abs(denom) < 1e-12:
            return 1e12 if evaluate_node(node.left, x) >= 0 else -1e12
        return evaluate_node(node.left, x) / denom
    else:
        return 0.0

# ============================================================
# SYMBOLIC DERIVATIVE
# ============================================================

def derivative(node, var='x'):
    """Return derivative of node with respect to var."""
    if node.is_terminal():
        if node.value == var:
            return Node(1.0)
        else:
            return Node(0.0)
    elif node.value == '+':
        return Node('+', derivative(node.left, var), derivative(node.right, var))
    elif node.value == '-':
        if node.right is None:
            # unary negation: d(-u)/dx = -du/dx
            return Node('-', derivative(node.left, var), None)
        return Node('-', derivative(node.left, var), derivative(node.right, var))
    elif node.value == '*':
        return Node('+',
                    Node('*', derivative(node.left, var), copy.deepcopy(node.right)),
                    Node('*', copy.deepcopy(node.left), derivative(node.right, var)))
    elif node.value == '/':
        u = copy.deepcopy(node.left)
        v = copy.deepcopy(node.right)
        u_prime = derivative(node.left, var)
        v_prime = derivative(node.right, var)
        return Node('/',
                    Node('-', Node('*', u_prime, v), Node('*', u, v_prime)),
                    Node('*', v, v))
    else:
        return Node(0.0)

# ============================================================
# CONSTANT OPTIMIZATION (Simple gradient-free local search)
# ============================================================

def optimize_constants(expr_node, x_data, y_data, max_iter=50):
    """
    Refine all constants in the expression tree using Nelder-Mead.
    This is a simple direct search that mutates constants and keeps
    the best combination.
    """
    # Collect all constant nodes
    constants = expr_node.collect_constants()
    if not constants:
        return expr_node

    def evaluate_with_constants(node, x, const_vals):
        """Evaluate with the given constant values."""
        # We'll walk the tree and substitute constants
        return evaluate_node(node, x)

    # We'll use a simple coordinate descent approach:
    # For each constant, try adding a small delta and see if fitness improves.
    # We'll do this for max_iter iterations.
    best_fitness = rmse_for_node(expr_node, x_data, y_data)
    best_node = copy.deepcopy(expr_node)

    for _ in range(max_iter):
        improved = False
        # Shuffle the constants order
        const_order = list(range(len(constants)))
        random.shuffle(const_order)
        for idx in const_order:
            c_node = constants[idx]
            original_val = c_node.value
            # Try small perturbations
            for delta in [-0.1, 0.1, -0.01, 0.01, -0.001, 0.001]:
                c_node.value = original_val + delta
                fitness = rmse_for_node(expr_node, x_data, y_data)
                if fitness < best_fitness:
                    best_fitness = fitness
                    best_node = copy.deepcopy(expr_node)
                    improved = True
                    break
                c_node.value = original_val
            if improved:
                break
        # If we haven't improved, reduce step size
        if not improved:
            break

    return best_node

def rmse_for_node(node, x_data, y_data):
    """Compute RMSE of node on data."""
    total = 0.0
    for x, y in zip(x_data, y_data):
        pred = evaluate_node(node, x)
        if math.isinf(pred) or math.isnan(pred):
            return float('inf')
        total += (pred - y) ** 2
    return math.sqrt(total / len(x_data))

# ============================================================
# GENETIC PROGRAMMING
# ============================================================

class GeneticProgram:
    def __init__(self, population_size=200, generations=100, max_depth=5):
        self.population_size = population_size
        self.generations = generations
        self.max_depth = max_depth
        self.operators = ['+', '-', '*', '/']
        self.population = []
        self.best_individual = None
        self.best_fitness = float('inf')

    def random_tree(self, depth):
        if depth >= self.max_depth or (depth > 0 and random.random() < 0.3):
            # Terminal
            if random.random() < 0.5:
                return Node('x')
            else:
                const = random.uniform(-5.0, 5.0)
                return Node(const)
        else:
            op = random.choice(self.operators)
            return Node(op, self.random_tree(depth+1), self.random_tree(depth+1))

    def fitness(self, node, x_data, y_data):
        return rmse_for_node(node, x_data, y_data)

    def tournament_select(self, fitnesses, tournament_size=5):
        idx = random.sample(range(len(self.population)), tournament_size)
        best_idx = min(idx, key=lambda i: fitnesses[i])
        return copy.deepcopy(self.population[best_idx])

    def mutate(self, node):
        if random.random() < 0.3:
            # Replace subtree with new random tree
            return self.random_tree(0)
        else:
            if node.is_terminal():
                if node.value != 'x':
                    node.value = random.uniform(-5.0, 5.0)
                return node
            else:
                if node.left is not None and random.random() < 0.5:
                    node.left = self.mutate(node.left)
                if node.right is not None and random.random() < 0.5:
                    node.right = self.mutate(node.right)
                return node

    def crossover(self, parent1, parent2):
        child1 = copy.deepcopy(parent1)
        child2 = copy.deepcopy(parent2)
        nodes1 = []
        nodes2 = []
        self.collect_nodes(child1, nodes1)
        self.collect_nodes(child2, nodes2)
        if not nodes1 or not nodes2:
            return child1, child2
        target1 = random.choice(nodes1)
        target2 = random.choice(nodes2)

        def replace_subtree(root, old_node, new_node):
            if root is old_node:
                return new_node
            if root.is_terminal():
                return root
            new_left = replace_subtree(root.left, old_node, new_node) if root.left else None
            new_right = replace_subtree(root.right, old_node, new_node) if root.right else None
            if new_left is root.left and new_right is root.right:
                return root
            return Node(root.value, new_left, new_right)

        new_child1 = replace_subtree(child1, target1, copy.deepcopy(target2))
        new_child2 = replace_subtree(child2, target2, copy.deepcopy(target1))

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

    def evolve(self, x_data, y_data):
        # Initialize population
        self.population = [self.random_tree(0) for _ in range(self.population_size)]
        self.best_individual = None
        self.best_fitness = float('inf')

        for gen in range(self.generations):
            # Evaluate fitness
            fitnesses = [self.fitness(ind, x_data, y_data) for ind in self.population]

            # Update best
            min_idx = min(range(len(fitnesses)), key=lambda i: fitnesses[i])
            if fitnesses[min_idx] < self.best_fitness:
                self.best_fitness = fitnesses[min_idx]
                self.best_individual = copy.deepcopy(self.population[min_idx])
                # Optimize constants of the best individual
                optimized = optimize_constants(self.best_individual, x_data, y_data)
                opt_fitness = self.fitness(optimized, x_data, y_data)
                if opt_fitness < self.best_fitness:
                    self.best_fitness = opt_fitness
                    self.best_individual = optimized

            # Create new population
            new_population = []
            # Elitism: keep best 2
            new_population.append(copy.deepcopy(self.best_individual))
            if len(self.population) >= 2:
                # also keep second best
                second_idx = min([i for i in range(len(fitnesses)) if i != min_idx],
                                 key=lambda i: fitnesses[i])
                new_population.append(copy.deepcopy(self.population[second_idx]))

            while len(new_population) < self.population_size:
                parent1 = self.tournament_select(fitnesses)
                parent2 = self.tournament_select(fitnesses)
                if random.random() < 0.7:
                    child1, child2 = self.crossover(parent1, parent2)
                else:
                    child1, child2 = copy.deepcopy(parent1), copy.deepcopy(parent2)

                if random.random() < 0.15:
                    child1 = self.mutate(child1)
                if random.random() < 0.15:
                    child2 = self.mutate(child2)

                # Occasionally optimize constants of children
                if random.random() < 0.05:
                    child1 = optimize_constants(child1, x_data, y_data, max_iter=10)
                if random.random() < 0.05:
                    child2 = optimize_constants(child2, x_data, y_data, max_iter=10)

                new_population.append(child1)
                if len(new_population) < self.population_size:
                    new_population.append(child2)

            self.population = new_population

        # Final constant optimization on the best individual
        self.best_individual = optimize_constants(self.best_individual, x_data, y_data, max_iter=100)
        self.best_fitness = self.fitness(self.best_individual, x_data, y_data)
        return self.best_individual

# ============================================================
# DISCOVERY ENGINE
# ============================================================

class AEGIS_Discovery_v4:
    def __init__(self):
        self.training: List[Observation] = []
        self.validation: List[Observation] = []

    def receive(self, observations: List[Observation]) -> None:
        self.training.extend(observations)

    @staticmethod
    def rmse(actual: List[float], predicted: List[float]) -> float:
        if not actual:
            return float("inf")
        return math.sqrt(sum((a - p) ** 2 for a, p in zip(actual, predicted)) / len(actual))

    def local_rates(self, observations: List[Observation]) -> List[Tuple[float, float]]:
        ordered = sorted(observations, key=lambda o: o.x)
        rates = []
        for i in range(len(ordered) - 1):
            x1, y1 = ordered[i].x, ordered[i].y
            x2, y2 = ordered[i + 1].x, ordered[i + 1].y
            dx = x2 - x1
            if abs(dx) < 1e-12:
                continue
            rates.append(((x1 + x2) / 2.0, (y2 - y1) / dx))
        return rates

    def validate_candidate(self, expr_node, x_data, y_data):
        if not self.validation:
            n = len(x_data)
            split = int(0.7 * n)
            x_val = x_data[split:]
            y_val = y_data[split:]
            val_obs = [Observation(x=x, y=y) for x, y in zip(x_val, y_val)]
        else:
            val_obs = self.validation

        rate_vals = self.local_rates(val_obs)
        if len(rate_vals) < 2:
            return None
        deriv_node = derivative(expr_node)
        actual_rates = [r for _, r in rate_vals]
        pred_rates = [evaluate_node(deriv_node, x) for x, _ in rate_vals]
        rate_error = self.rmse(actual_rates, pred_rates)

        ordered = sorted(val_obs, key=lambda o: o.x)
        if len(ordered) < 2:
            return None
        x0 = ordered[0].x
        y0 = ordered[0].y
        x_vals = [o.x for o in ordered]

        def integrate_derivative(deriv, xs, y0):
            result = [y0]
            current = y0
            for i in range(1, len(xs)):
                dx = xs[i] - xs[i-1]
                avg_rate = (evaluate_node(deriv, xs[i-1]) + evaluate_node(deriv, xs[i])) / 2.0
                current += avg_rate * dx
                result.append(current)
            return result

        recon_y = integrate_derivative(deriv_node, x_vals, y0)
        actual_y = [o.y for o in ordered]
        recon_error = self.rmse(actual_y, recon_y)

        if len(ordered) < 3:
            pred_error = float("inf")
        else:
            anchor = ordered[0]
            targets = ordered[1:]
            x_targets = [t.x for t in targets]

            def integrate_to_target(xs, anchor_x, anchor_y, deriv):
                preds = []
                for tx in xs:
                    steps = 100
                    dx = (tx - anchor_x) / steps
                    current = anchor_y
                    for i in range(steps):
                        x1 = anchor_x + i*dx
                        x2 = anchor_x + (i+1)*dx
                        avg_rate = (evaluate_node(deriv, x1) + evaluate_node(deriv, x2)) / 2.0
                        current += avg_rate * dx
                    preds.append(current)
                return preds

            preds = integrate_to_target(x_targets, anchor.x, anchor.y, deriv_node)
            actuals = [t.y for t in targets]
            pred_error = self.rmse(actuals, preds)

        gates_passed = 0
        if rate_error < 0.10: gates_passed += 1
        if recon_error < 0.10: gates_passed += 1
        if pred_error < 0.10: gates_passed += 1

        return {
            'expr': expr_node,
            'rate_error': rate_error,
            'recon_error': recon_error,
            'pred_error': pred_error,
            'gates_passed': gates_passed
        }

    def run(self, x_values: List[float], y_values: List[float]) -> Dict:
        if len(x_values) != len(y_values) or len(x_values) < 6:
            return {"status": "INSUFFICIENT_DATA"}

        paired = sorted(zip(x_values, y_values), key=lambda p: p[0])
        split = int(0.7 * len(paired))
        train_pairs = paired[:split]
        val_pairs = paired[split:]
        self.training = [Observation(x=x, y=y) for x, y in train_pairs]
        self.validation = [Observation(x=x, y=y) for x, y in val_pairs]

        x_train = [o.x for o in self.training]
        y_train = [o.y for o in self.training]

        gp = GeneticProgram(population_size=200, generations=100, max_depth=5)
        best_expr = gp.evolve(x_train, y_train)

        print(f"[GP] Best fitness (train RMSE): {gp.best_fitness:.6f}")
        print(f"[GP] Best expression: {repr(best_expr)}")

        validation_result = self.validate_candidate(best_expr, x_values, y_values)
        if validation_result is None:
            return {
                "status": "REJECTED",
                "reason": "Validation failed due to insufficient data."
            }

        if validation_result['gates_passed'] == 3:
            return {
                "status": "PROMOTED",
                "expression": repr(best_expr),
                "rate_error": validation_result['rate_error'],
                "recon_error": validation_result['recon_error'],
                "pred_error": validation_result['pred_error'],
                "gates_passed": validation_result['gates_passed']
            }
        else:
            return {
                "status": "REJECTED",
                "reason": f"Gates passed: {validation_result['gates_passed']}/3",
                "rate_error": validation_result['rate_error'],
                "recon_error": validation_result['recon_error'],
                "pred_error": validation_result['pred_error']
            }

# ============================================================
# DEMONSTRATION
# ============================================================

def main():
    random.seed(42)

    print("=" * 72)
    print("AEGIS DISCOVERY ENGINE v4 – GP with Constant Optimization")
    print("=" * 72)
    print()

    # Quadratic data
    print("[1] Quadratic data (y = x^2 + 0.35x + noise)")
    x_vals = [-1.73, -1.41, -1.08, -0.82, -0.53, -0.21,
              0.14, 0.39, 0.67, 0.91, 1.18, 1.47, 1.82]
    y_vals = [(x*x) + 0.35*x + random.gauss(0.0, 0.01) for x in x_vals]
    engine = AEGIS_Discovery_v4()
    result = engine.run(x_vals, y_vals)
    print(f"  Status: {result['status']}")
    if result['status'] == 'PROMOTED':
        print(f"  Expression: {result['expression']}")
        print(f"  Rate error: {result['rate_error']:.4f}")
        print(f"  Recon error: {result['recon_error']:.4f}")
        print(f"  Pred error: {result['pred_error']:.4f}")
    else:
        print(f"  Reason: {result.get('reason', 'N/A')}")
    print()

    # Linear data
    print("[2] Linear data (y = 3x + 1)")
    x_linear = [-3, -2, -1, 0, 1, 2, 3, 4, 5]
    y_linear = [3*x + 1 for x in x_linear]
    engine = AEGIS_Discovery_v4()
    result = engine.run(x_linear, y_linear)
    print(f"  Status: {result['status']}")
    if result['status'] == 'PROMOTED':
        print(f"  Expression: {result['expression']}")
    print()

    # Exponential data
    print("[3] Exponential data (y = 2*exp(0.5*x) + 1)")
    x_exp = [i/2.0 for i in range(-4, 6)]
    y_exp = [2*math.exp(0.5*x) + 1 + random.gauss(0.0, 0.02) for x in x_exp]
    engine = AEGIS_Discovery_v4()
    result = engine.run(x_exp, y_exp)
    print(f"  Status: {result['status']}")
    if result['status'] == 'PROMOTED':
        print(f"  Expression: {result['expression']}")
    print()

    # Pure noise
    print("[4] Pure noise")
    random.seed(99)
    x_noise = [i/10.0 for i in range(30)]
    y_noise = [random.gauss(0.0, 1.0) for _ in range(30)]
    engine = AEGIS_Discovery_v4()
    result = engine.run(x_noise, y_noise)
    print(f"  Status: {result['status']}")
    if result['status'] == 'REJECTED':
        print(f"  Reason: {result.get('reason', 'N/A')}")
    print("=" * 72)

if __name__ == "__main__":
    main()
