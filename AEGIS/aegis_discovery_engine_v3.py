#!/data/data/com.termux/files/usr/bin/python

"""
AEGIS Discovery Engine v3 – Genetic Programming Symbolic Regression

This engine searches over a space of mathematical expressions to find a function
that fits the data. It uses genetic programming with:
- Operators: +, -, *, /, sin, cos, exp, log
- Terminals: x, random constants
- Fitness: RMSE on training data (curve fit)
- Validation: three gates (rate, reconstruction, prediction)
- Promotion: only if all three gates pass

The engine discovers an arbitrary function, not just fixed forms.
"""

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple, Callable
import copy

# ============================================================
# NODE REPRESENTATION
# ============================================================

class Node:
    """Expression tree node."""
    def __init__(self, value, left=None, right=None):
        self.value = value      # operator name or 'x' or constant
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
        return Node('-', derivative(node.left, var), derivative(node.right, var))
    elif node.value == '*':
        # u'v + uv'
        return Node('+',
                    Node('*', derivative(node.left, var), copy.deepcopy(node.right)),
                    Node('*', copy.deepcopy(node.left), derivative(node.right, var)))
    elif node.value == '/':
        # (u'v - uv')/v^2
        u = copy.deepcopy(node.left)
        v = copy.deepcopy(node.right)
        u_prime = derivative(node.left, var)
        v_prime = derivative(node.right, var)
        return Node('/',
                    Node('-', Node('*', u_prime, v), Node('*', u, v_prime)),
                    Node('*', v, v))
    elif node.value == 'sin':
        return Node('*', Node('cos', copy.deepcopy(node.left)), derivative(node.left, var))
    elif node.value == 'cos':
        return Node('*', Node('-', Node('sin', copy.deepcopy(node.left))), derivative(node.left, var))
    elif node.value == 'exp':
        return Node('*', copy.deepcopy(node), derivative(node.left, var))
    elif node.value == 'log':
        return Node('/', derivative(node.left, var), copy.deepcopy(node.left))
    else:
        return Node(0.0)

# ============================================================
# EVALUATION
# ============================================================

def evaluate_node(node, x):
    """Evaluate expression tree at x."""
    if node.is_terminal():
        if node.value == 'x':
            return x
        else:
            return float(node.value)
    elif node.value == '+':
        return evaluate_node(node.left, x) + evaluate_node(node.right, x)
    elif node.value == '-':
        return evaluate_node(node.left, x) - evaluate_node(node.right, x)
    elif node.value == '*':
        return evaluate_node(node.left, x) * evaluate_node(node.right, x)
    elif node.value == '/':
        denom = evaluate_node(node.right, x)
        if abs(denom) < 1e-12:
            return 1e12  # large penalty to avoid division by zero
        return evaluate_node(node.left, x) / denom
    elif node.value == 'sin':
        return math.sin(evaluate_node(node.left, x))
    elif node.value == 'cos':
        return math.cos(evaluate_node(node.left, x))
    elif node.value == 'exp':
        return math.exp(evaluate_node(node.left, x))
    elif node.value == 'log':
        val = evaluate_node(node.left, x)
        if val <= 0:
            return -1e12  # penalty
        return math.log(val)
    else:
        return 0.0

# ============================================================
# GENETIC PROGRAMMING
# ============================================================

class GeneticProgram:
    def __init__(self, population_size=100, generations=50, max_depth=5,
                 operators=['+', '-', '*', '/', 'sin', 'cos', 'exp', 'log'],
                 terminals=['x']):
        self.population_size = population_size
        self.generations = generations
        self.max_depth = max_depth
        self.operators = operators
        self.terminals = terminals
        self.population = []
        self.best_individual = None
        self.best_fitness = float('inf')

    def random_tree(self, depth):
        """Generate a random expression tree."""
        if depth >= self.max_depth or (depth > 0 and random.random() < 0.3):
            # Terminal
            if random.random() < 0.5:
                return Node('x')
            else:
                const = random.uniform(-5.0, 5.0)
                return Node(const)
        else:
            # Operator
            op = random.choice(self.operators)
            if op in ['sin', 'cos', 'exp', 'log']:
                return Node(op, self.random_tree(depth+1), None)
            else:
                return Node(op, self.random_tree(depth+1), self.random_tree(depth+1))

    def fitness(self, node, x_data, y_data):
        """Fitness: RMSE of the expression on the data."""
        total = 0.0
        for x, y in zip(x_data, y_data):
            pred = evaluate_node(node, x)
            if math.isinf(pred) or math.isnan(pred):
                return float('inf')
            total += (pred - y) ** 2
        return math.sqrt(total / len(x_data))

    def tournament_select(self, fitnesses, tournament_size=3):
        idx = random.sample(range(len(self.population)), tournament_size)
        best_idx = min(idx, key=lambda i: fitnesses[i])
        return copy.deepcopy(self.population[best_idx])

    def mutate(self, node):
        """Mutate a tree by replacing a subtree with a random one."""
        if random.random() < 0.5:
            # Replace current node with a new random subtree
            return self.random_tree(0)
        else:
            # Mutate a random subtree
            if node.is_terminal():
                if random.random() < 0.5:
                    # change constant
                    if node.value != 'x':
                        node.value = random.uniform(-5.0, 5.0)
                return node
            else:
                if node.left is not None:
                    node.left = self.mutate(node.left)
                if node.right is not None:
                    node.right = self.mutate(node.right)
                return node

    def crossover(self, parent1, parent2):
        """Crossover: swap subtrees between parents."""
        child1 = copy.deepcopy(parent1)
        child2 = copy.deepcopy(parent2)
        # Pick random nodes in each tree
        nodes1 = []
        nodes2 = []
        self.collect_nodes(child1, nodes1)
        self.collect_nodes(child2, nodes2)
        if not nodes1 or not nodes2:
            return child1, child2
        node1 = random.choice(nodes1)
        node2 = random.choice(nodes2)
        # Swap values and children (shallow swap)
        # For simplicity, we'll swap the entire node structure
        # Since we need to keep references, we'll swap the subtrees
        # We'll just replace node1 with a copy of node2, and vice versa
        # But this might break parent pointers, we'll do deep copy
        # Better: replace the node in the tree
        # We'll implement by finding parent pointers? Instead, we'll rebuild.
        # Simpler approach: pick two subtrees and swap them by value assignment
        # Use a helper to replace a node
        def replace_node(root, target, replacement):
            if root is target:
                return replacement
            if root.is_terminal():
                return root
            if root.left is not None:
                root.left = replace_node(root.left, target, replacement)
            if root.right is not None:
                root.right = replace_node(root.right, target, replacement)
            return root
        # We'll replace node1 in child1 with a copy of node2, and node2 in child2 with a copy of node1
        # But we need to ensure depth limits
        # For simplicity, we'll just return parents if mutation not performed
        # We'll do a safer crossover: pick two subtrees and swap them if they don't exceed depth limit
        def depth(node):
            if node.is_terminal():
                return 0
            return 1 + max(depth(node.left) if node.left else 0,
                           depth(node.right) if node.right else 0)
        # We'll enforce max depth after crossover
        # If too deep, we'll just return parents
        # We'll use a simpler approach: swap a subtree from parent1 with a random subtree from parent2
        # But we need to handle reference.
        # We'll implement a new crossover: pick a random node in parent1 and replace it with a random node from parent2
        # But we need to ensure we don't modify parent2.
        # We'll just create new children by copying and swapping.
        # I'll implement a simpler crossover: exchange subtrees between two copies.
        # This is a common GP crossover.
        # We'll use a function to get all nodes.
        # Then replace a node in child1 with a node from child2.
        # We'll just swap the values and children? That's tricky.
        # Let's do subtree swap: randomly select a node in child1, and a node in child2, and swap them (by replacing the node in child1 with a copy of the node in child2, and vice versa)
        # We need parent pointers to replace easily. Instead, we'll use a recursive function that returns a new tree with the swap.
        # This is getting complex. For a working demonstration, we'll implement a simpler crossover: one-point crossover on the expression tree.
        # We'll just return the parents with a random mutation instead.
        # Or we can implement a simple random subtree swap by building new trees from the nodes.
        # Given time, I'll implement a simple crossover: pick a node in parent1, pick a node in parent2, and swap their subtrees by reconstructing the tree.
        # We'll just create new children by replacing the node in parent1 with a copy of node2, and node2 with a copy of node1.
        # We'll need to find parents. We'll implement a helper that returns a new tree with the replacement.
        def replace_subtree(root, old_node, new_node):
            if root is old_node:
                return new_node
            if root.is_terminal():
                return root
            new_left = replace_subtree(root.left, old_node, new_node) if root.left else None
            new_right = replace_subtree(root.right, old_node, new_node) if root.right else None
            if new_left is root.left and new_right is root.right:
                return root
            new_root = Node(root.value, new_left, new_right)
            return new_root
        # We'll pick nodes
        nodes1 = []
        self.collect_nodes(child1, nodes1)
        nodes2 = []
        self.collect_nodes(child2, nodes2)
        if not nodes1 or not nodes2:
            return child1, child2
        target1 = random.choice(nodes1)
        target2 = random.choice(nodes2)
        # Create new children
        new_child1 = replace_subtree(child1, target1, copy.deepcopy(target2))
        new_child2 = replace_subtree(child2, target2, copy.deepcopy(target1))
        # Check depth limits
        if depth(new_child1) <= self.max_depth and depth(new_child2) <= self.max_depth:
            return new_child1, new_child2
        else:
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
        """Run the genetic programming evolution."""
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

            # Create new population
            new_population = []
            # Elitism: keep best
            new_population.append(copy.deepcopy(self.best_individual))
            while len(new_population) < self.population_size:
                parent1 = self.tournament_select(fitnesses)
                parent2 = self.tournament_select(fitnesses)
                # Crossover
                if random.random() < 0.8:
                    child1, child2 = self.crossover(parent1, parent2)
                else:
                    child1, child2 = copy.deepcopy(parent1), copy.deepcopy(parent2)
                # Mutation
                if random.random() < 0.1:
                    child1 = self.mutate(child1)
                if random.random() < 0.1:
                    child2 = self.mutate(child2)
                new_population.append(child1)
                if len(new_population) < self.population_size:
                    new_population.append(child2)
            self.population = new_population

        return self.best_individual

# ============================================================
# DISCOVERY ENGINE (using GP)
# ============================================================

class AEGIS_Discovery_v3:
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
        """
        Validate the discovered expression using the three gates:
        1. Rate error: derivative matches local rates.
        2. Reconstruction error: integrate derivative from first point.
        3. Prediction error: predict from anchor.
        """
        # Split data into train and validation if not already done
        # We'll use the same data for validation (since we have a separate validation set)
        # For simplicity, we'll use the provided validation set.
        if not self.validation:
            # If no validation set, use 70% train, 30% val
            n = len(x_data)
            split = int(0.7 * n)
            x_val = x_data[split:]
            y_val = y_data[split:]
            val_obs = [Observation(x=x, y=y) for x, y in zip(x_val, y_val)]
        else:
            val_obs = self.validation

        # 1. Rate error: compare derivative to local rates
        rate_vals = self.local_rates(val_obs)
        if len(rate_vals) < 2:
            return None
        # Compute derivative expression
        deriv_node = derivative(expr_node)
        actual_rates = [r for _, r in rate_vals]
        pred_rates = [evaluate_node(deriv_node, x) for x, _ in rate_vals]
        rate_error = self.rmse(actual_rates, pred_rates)

        # 2. Reconstruction error: integrate numerically from first point
        ordered = sorted(val_obs, key=lambda o: o.x)
        if len(ordered) < 2:
            return None
        x0 = ordered[0].x
        y0 = ordered[0].y
        # Trapezoidal integration of derivative
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

        # 3. Prediction error: from anchor (first point) to all others
        if len(ordered) < 3:
            pred_error = float("inf")
        else:
            anchor = ordered[0]
            targets = ordered[1:]
            x_targets = [t.x for t in targets]
            # Predict by integrating derivative from anchor.x to each target.x
            def integrate_to_target(xs, anchor_x, anchor_y, deriv):
                preds = []
                for tx in xs:
                    # integrate from anchor_x to tx
                    # We'll use adaptive Simpson or trapezoidal with many steps
                    # Simple: use 100 steps
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

        # Split data into training (for GP) and validation (for gates)
        paired = sorted(zip(x_values, y_values), key=lambda p: p[0])
        split = int(0.7 * len(paired))
        train_pairs = paired[:split]
        val_pairs = paired[split:]
        self.training = [Observation(x=x, y=y) for x, y in train_pairs]
        self.validation = [Observation(x=x, y=y) for x, y in val_pairs]

        # Prepare training data for GP
        x_train = [o.x for o in self.training]
        y_train = [o.y for o in self.training]

        # Run GP
        gp = GeneticProgram(population_size=50, generations=30, max_depth=5)
        best_expr = gp.evolve(x_train, y_train)
        print(f"[GP] Best fitness: {gp.best_fitness:.4f}")
        print(f"[GP] Best expression: {repr(best_expr)}")

        # Validate the best expression
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
    print("AEGIS DISCOVERY ENGINE v3 – Genetic Programming Discovery")
    print("=" * 72)
    print()

    # Quadratic data
    print("[1] Quadratic data (y = x^2 + 0.35x + noise)")
    x_vals = [-1.73, -1.41, -1.08, -0.82, -0.53, -0.21,
              0.14, 0.39, 0.67, 0.91, 1.18, 1.47, 1.82]
    y_vals = [(x*x) + 0.35*x + random.gauss(0.0, 0.01) for x in x_vals]
    engine = AEGIS_Discovery_v3()
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
    engine = AEGIS_Discovery_v3()
    result = engine.run(x_linear, y_linear)
    print(f"  Status: {result['status']}")
    if result['status'] == 'PROMOTED':
        print(f"  Expression: {result['expression']}")
    print()

    # Exponential data
    print("[3] Exponential data (y = 2*exp(0.5*x) + 1)")
    x_exp = [i/2.0 for i in range(-4, 6)]
    y_exp = [2*math.exp(0.5*x) + 1 + random.gauss(0.0, 0.02) for x in x_exp]
    engine = AEGIS_Discovery_v3()
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
    engine = AEGIS_Discovery_v3()
    result = engine.run(x_noise, y_noise)
    print(f"  Status: {result['status']}")
    if result['status'] == 'REJECTED':
        print(f"  Reason: {result.get('reason', 'N/A')}")
    print("=" * 72)

if __name__ == "__main__":
    main()
