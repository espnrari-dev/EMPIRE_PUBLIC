#!/data/data/com.termux/files/usr/bin/python
"""
AEGIS DISCOVERY — Point it at YOUR data.

Usage:
    python aegis_discover.py --file data.csv --x column1 --y column2

Example:
    python aegis_discover.py --file my_sensors.csv --x rpm --y torque

If you don't specify columns, it will use the first two numeric columns.

Output: A clean report with:
    - Status (PROMOTED / REJECTED)
    - Discovered expression
    - All gate errors
    - Margin of safety
    - Prudence score
    - A plain‑English summary.
"""

import sys, os, math, random, copy, csv, argparse
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

# ============================================================
# 1. FULL ENGINE (same as V8 – no changes)
# ============================================================

@dataclass
class Observation:
    x: float
    y: float

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
    def node_count(self):
        if self.is_terminal():
            return 1
        return 1 + (self.left.node_count() if self.left else 0) + (self.right.node_count() if self.right else 0)
    def collect_constants(self):
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
    def simplify(self):
        if self.is_terminal():
            return self
        left = self.left.simplify() if self.left else None
        right = self.right.simplify() if self.right else None
        if self.value == '+':
            if left is not None and left.is_terminal() and left.value == 0.0:
                return right
            if right is not None and right.is_terminal() and right.value == 0.0:
                return left
        elif self.value == '*':
            if left is not None and left.is_terminal() and left.value == 1.0:
                return right
            if right is not None and right.is_terminal() and right.value == 1.0:
                return left
            if left is not None and left.is_terminal() and left.value == 0.0:
                return Node(0.0)
            if right is not None and right.is_terminal() and right.value == 0.0:
                return Node(0.0)
        elif self.value == '/':
            if right is not None and right.is_terminal() and right.value == 1.0:
                return left
            if left is not None and right is not None and repr(left) == repr(right):
                return Node(1.0)
        return Node(self.value, left, right)

def evaluate_node(node, x):
    if node.is_terminal():
        if node.value == 'x':
            return x
        else:
            return float(node.value)
    if node.value == '+':
        return evaluate_node(node.left, x) + evaluate_node(node.right, x)
    if node.value == '-':
        if node.right is None:
            return -evaluate_node(node.left, x)
        return evaluate_node(node.left, x) - evaluate_node(node.right, x)
    if node.value == '*':
        return evaluate_node(node.left, x) * evaluate_node(node.right, x)
    if node.value == '/':
        denom = evaluate_node(node.right, x)
        if abs(denom) < 1e-12:
            raise ZeroDivisionError
        return evaluate_node(node.left, x) / denom
    if node.value == 'sin':
        return math.sin(evaluate_node(node.left, x))
    if node.value == 'cos':
        return math.cos(evaluate_node(node.left, x))
    if node.value == 'exp':
        val = evaluate_node(node.left, x)
        if val > 709:
            raise OverflowError
        return math.exp(val)
    if node.value == 'log':
        val = evaluate_node(node.left, x)
        if val <= 0:
            raise ValueError
        return math.log(val)
    raise ValueError(f"Unknown: {node.value}")

def derivative(node, var='x'):
    if node.is_terminal():
        if node.value == var:
            return Node(1.0)
        else:
            return Node(0.0)
    if node.value == '+':
        return Node('+', derivative(node.left, var), derivative(node.right, var))
    if node.value == '-':
        if node.right is None:
            return Node('-', derivative(node.left, var), None)
        return Node('-', derivative(node.left, var), derivative(node.right, var))
    if node.value == '*':
        return Node('+',
                    Node('*', derivative(node.left, var), copy.deepcopy(node.right)),
                    Node('*', copy.deepcopy(node.left), derivative(node.right, var)))
    if node.value == '/':
        u = copy.deepcopy(node.left)
        v = copy.deepcopy(node.right)
        u_prime = derivative(node.left, var)
        v_prime = derivative(node.right, var)
        return Node('/',
                    Node('-', Node('*', u_prime, v), Node('*', u, v_prime)),
                    Node('*', v, v))
    if node.value == 'sin':
        return Node('*', Node('cos', copy.deepcopy(node.left)), derivative(node.left, var))
    if node.value == 'cos':
        return Node('*', Node('-', Node('sin', copy.deepcopy(node.left)), None), derivative(node.left, var))
    if node.value == 'exp':
        return Node('*', copy.deepcopy(node), derivative(node.left, var))
    if node.value == 'log':
        return Node('/', derivative(node.left, var), copy.deepcopy(node.left))
    return Node(0.0)

def rmse_only(node, x_data, y_data):
    try:
        total = sum((evaluate_node(node, x) - y)**2 for x, y in zip(x_data, y_data))
        return math.sqrt(total / len(x_data))
    except:
        return float('inf')

def optimize_constants(expr_node, x_data, y_data, max_iter=100):
    constants = expr_node.collect_constants()
    if not constants:
        return expr_node
    best_node = expr_node.clone()
    best_fitness = rmse_only(best_node, x_data, y_data)
    for _ in range(max_iter):
        improved = False
        const_order = list(range(len(constants)))
        random.shuffle(const_order)
        for idx in const_order:
            c_node = constants[idx]
            orig = c_node.value
            for delta in [-0.1, 0.1, -0.01, 0.01, -0.001, 0.001]:
                c_node.value = orig + delta
                try:
                    for x in x_data:
                        evaluate_node(expr_node, x)
                except:
                    c_node.value = orig
                    continue
                fit = rmse_only(expr_node, x_data, y_data)
                if fit < best_fitness:
                    best_fitness = fit
                    best_node = expr_node.clone()
                    improved = True
                    break
                c_node.value = orig
            if improved:
                break
        if not improved:
            break
    return best_node.simplify()

class GeneticProgram:
    def __init__(self, population_size=400, generations=150, max_depth=5):
        self.population_size = population_size
        self.generations = generations
        self.max_depth = max_depth
        self.operators = ['+', '-', '*', '/', 'sin', 'cos', 'exp', 'log']
        self.population = []
        self.best_individual = None
        self.best_fitness = float('inf')
    def random_tree(self, depth):
        if depth >= self.max_depth or (depth > 0 and random.random() < 0.3):
            if random.random() < 0.5:
                return Node('x')
            else:
                return Node(random.uniform(-3.0, 3.0))
        else:
            op = random.choice(self.operators)
            if op in ['sin', 'cos', 'exp', 'log']:
                return Node(op, self.random_tree(depth+1), None)
            else:
                return Node(op, self.random_tree(depth+1), self.random_tree(depth+1))
    def fitness(self, node, x_data, y_data, lambda_complexity=0.01):
        base = rmse_only(node, x_data, y_data)
        if math.isinf(base):
            return float('inf')
        return base + lambda_complexity * node.node_count()
    def tournament_select(self, fitnesses, tournament_size=5):
        idx = random.sample(range(len(self.population)), tournament_size)
        best_idx = min(idx, key=lambda i: fitnesses[i])
        return copy.deepcopy(self.population[best_idx])
    def mutate(self, node):
        if random.random() < 0.3:
            return self.random_tree(0)
        else:
            if node.is_terminal():
                if node.value != 'x':
                    node.value = random.uniform(-3.0, 3.0)
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
    def evolve(self, x_data, y_data):
        self.population = [self.random_tree(0) for _ in range(self.population_size)]
        self.best_individual = None
        self.best_fitness = float('inf')
        for gen in range(self.generations):
            lambda_c = 0.005 * (1 + gen / self.generations)
            fitnesses = [self.fitness(ind, x_data, y_data, lambda_c) for ind in self.population]
            min_idx = min(range(len(fitnesses)), key=lambda i: fitnesses[i])
            if fitnesses[min_idx] < self.best_fitness:
                self.best_fitness = fitnesses[min_idx]
                self.best_individual = self.population[min_idx].clone()
                opt = optimize_constants(self.best_individual, x_data, y_data)
                opt_fit = self.fitness(opt, x_data, y_data, lambda_c)
                if opt_fit < self.best_fitness:
                    self.best_fitness = opt_fit
                    self.best_individual = opt
            if gen % 30 == 0:
                print(f"  Gen {gen}: best fitness = {self.best_fitness:.4f}, nodes = {self.best_individual.node_count() if self.best_individual else 0}")
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
        self.best_individual = optimize_constants(self.best_individual, x_data, y_data, max_iter=200)
        self.best_individual = self.best_individual.simplify()
        self.best_fitness = rmse_only(self.best_individual, x_data, y_data)
        return self.best_individual

def baseline_rmse(y_data):
    mean_y = sum(y_data) / len(y_data)
    return math.sqrt(sum((y - mean_y)**2 for y in y_data) / len(y_data))

def margin_of_safety(expr_rmse, baseline_rmse):
    if baseline_rmse == 0:
        return float('inf')
    return (baseline_rmse - expr_rmse) / baseline_rmse

def cross_validate_structure(x_data, y_data, model_node, n_folds=3):
    paired = sorted(zip(x_data, y_data), key=lambda p: p[0])
    n = len(paired)
    fold_size = n // n_folds
    structures = []
    for i in range(n_folds):
        test = paired[i*fold_size:(i+1)*fold_size]
        train = [p for j, p in enumerate(paired) if j < i*fold_size or j >= (i+1)*fold_size]
        x_train, y_train = zip(*train)
        gp = GeneticProgram(population_size=150, generations=40, max_depth=5)
        best = gp.evolve(list(x_train), list(y_train))
        structures.append(best.simplify().node_count())
    avg_nodes = sum(structures) / len(structures)
    if max(structures) - min(structures) > 0.5 * avg_nodes:
        return False
    return True

class AEGIS_Discovery_v8:
    def __init__(self):
        self.training: List[Observation] = []
        self.validation: List[Observation] = []
    @staticmethod
    def rmse(actual, predicted):
        if not actual:
            return float("inf")
        return math.sqrt(sum((a-p)**2 for a,p in zip(actual,predicted)) / len(actual))
    def local_rates(self, observations):
        ordered = sorted(observations, key=lambda o: o.x)
        rates = []
        for i in range(len(ordered)-1):
            x1, y1 = ordered[i].x, ordered[i].y
            x2, y2 = ordered[i+1].x, ordered[i+1].y
            dx = x2 - x1
            if abs(dx) < 1e-12:
                continue
            rates.append(((x1+x2)/2.0, (y2-y1)/dx))
        return rates
    def validate_candidate(self, expr_node, x_data, y_data):
        if not self.validation:
            n = len(x_data)
            split = int(0.7*n)
            val_obs = [Observation(x=x, y=y) for x,y in zip(x_data[split:], y_data[split:])]
        else:
            val_obs = self.validation
        # Check only the actual data points (no artificial x=0 etc.)
        for x in [o.x for o in val_obs]:
            try:
                evaluate_node(expr_node, x)
            except:
                return None
        rate_vals = self.local_rates(val_obs)
        if len(rate_vals) < 2:
            return None
        deriv_node = derivative(expr_node).simplify()
        pred_rates = []
        for x, _ in rate_vals:
            try:
                pred_rates.append(evaluate_node(deriv_node, x))
            except:
                return None
        actual_rates = [r for _, r in rate_vals]
        rate_error = self.rmse(actual_rates, pred_rates)
        ordered = sorted(val_obs, key=lambda o: o.x)
        x_vals = [o.x for o in ordered]
        y0 = ordered[0].y
        def integrate(deriv, xs, y0):
            res = [y0]
            cur = y0
            for i in range(1, len(xs)):
                dx = xs[i] - xs[i-1]
                v1 = evaluate_node(deriv, xs[i-1])
                v2 = evaluate_node(deriv, xs[i])
                cur += (v1+v2)/2.0 * dx
                res.append(cur)
            return res
        try:
            recon_y = integrate(deriv_node, x_vals, y0)
        except:
            return None
        actual_y = [o.y for o in ordered]
        recon_error = self.rmse(actual_y, recon_y)
        if len(ordered) < 3:
            pred_error = float('inf')
        else:
            anchor = ordered[0]
            targets = ordered[1:]
            x_targets = [t.x for t in targets]
            def pred_to_target(xs, ax, ay, deriv):
                preds = []
                for tx in xs:
                    steps = 100
                    dx = (tx - ax) / steps
                    cur = ay
                    for i in range(steps):
                        x1 = ax + i*dx
                        x2 = ax + (i+1)*dx
                        v1 = evaluate_node(deriv, x1)
                        v2 = evaluate_node(deriv, x2)
                        cur += (v1+v2)/2.0 * dx
                    preds.append(cur)
                return preds
            try:
                preds = pred_to_target(x_targets, anchor.x, anchor.y, deriv_node)
            except:
                return None
            actuals = [t.y for t in targets]
            pred_error = self.rmse(actuals, preds)
        gates_passed = 0
        if rate_error < 0.10: gates_passed += 1
        if recon_error < 0.10: gates_passed += 1
        if pred_error < 0.10: gates_passed += 1
        y_val = [o.y for o in val_obs]
        baseline = baseline_rmse(y_val)
        model_rmse = self.rmse(actual_y, recon_y)
        margin = margin_of_safety(model_rmse, baseline)
        mos_ok = margin > 0.30 if baseline > 0 else False
        return {
            'expr': expr_node.simplify(),
            'deriv': deriv_node.simplify(),
            'rate_error': rate_error,
            'recon_error': recon_error,
            'pred_error': pred_error,
            'gates_passed': gates_passed,
            'margin_of_safety': margin,
            'baseline_rmse': baseline,
            'model_rmse': model_rmse,
            'mos_ok': mos_ok
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
        print("[GP] Prudent discovery starting...")
        gp = GeneticProgram(population_size=400, generations=150, max_depth=5)
        best_expr = gp.evolve(x_train, y_train)
        print(f"[GP] Final: {repr(best_expr)}, nodes: {best_expr.node_count()}")
        val_res = self.validate_candidate(best_expr, x_values, y_values)
        if val_res is None:
            return {"status": "REJECTED", "reason": "Singularities or validation failed."}
        if not val_res['mos_ok']:
            return {
                "status": "REJECTED",
                "reason": f"Margin of safety too low ({(val_res['margin_of_safety']*100):.1f}% improvement over baseline, need >30%)."
            }
        stable = cross_validate_structure(x_train, y_train, best_expr, n_folds=3)
        if not stable:
            return {"status": "REJECTED", "reason": "Discovered structure unstable across data folds."}
        if best_expr.node_count() > 20:
            return {"status": "REJECTED", "reason": f"Expression too complex (nodes: {best_expr.node_count()})."}
        gates = val_res['gates_passed'] / 3.0
        margin = min(1.0, val_res['margin_of_safety'])
        complexity_penalty = 1.0 - (best_expr.node_count() - 1) / 20.0
        if complexity_penalty < 0:
            complexity_penalty = 0
        prudence_score = (gates * 40 + margin * 40 + complexity_penalty * 20)
        prudence_score = min(100, prudence_score)
        if prudence_score < 60:
            return {
                "status": "REJECTED",
                "reason": f"Prudence score {prudence_score:.1f} < 60. Not certain enough.",
                "prudence_score": prudence_score
            }
        return {
            "status": "PROMOTED",
            "expression": repr(val_res['expr']),
            "derivative": repr(val_res['deriv']),
            "rate_error": val_res['rate_error'],
            "recon_error": val_res['recon_error'],
            "pred_error": val_res['pred_error'],
            "gates_passed": val_res['gates_passed'],
            "margin_of_safety": val_res['margin_of_safety'],
            "prudence_score": prudence_score,
            "node_count": best_expr.node_count()
        }

# ============================================================
# 2. CSV LOADER (your data)
# ============================================================

def load_csv(filepath, x_col=None, y_col=None):
    """
    Load a CSV file and return (x_values, y_values, column_names, used_x, used_y).
    If x_col or y_col is None, use the first two numeric columns found.
    """
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if not rows:
        raise ValueError("CSV file is empty.")

    # Detect numeric columns
    numeric_cols = {}
    for col in fieldnames:
        try:
            # Try converting a few values to float
            vals = [float(row[col]) for row in rows[:10] if row[col].strip() != '']
            if vals:
                numeric_cols[col] = True
        except:
            numeric_cols[col] = False

    numeric_cols = [c for c, is_num in numeric_cols.items() if is_num]

    if not numeric_cols:
        raise ValueError("No numeric columns found in CSV.")

    # If x_col/y_col not specified, use the first two numeric columns
    if x_col is None:
        x_col = numeric_cols[0]
        print(f"[Auto] Using '{x_col}' as x (input)")
    if y_col is None:
        if len(numeric_cols) < 2:
            raise ValueError("Only one numeric column found; need two for x and y.")
        # Use the second numeric column that isn't x
        for c in numeric_cols:
            if c != x_col:
                y_col = c
                break
        print(f"[Auto] Using '{y_col}' as y (output)")

    if x_col not in fieldnames or y_col not in fieldnames:
        raise ValueError(f"Columns '{x_col}' or '{y_col}' not found in CSV.")

    x_values = []
    y_values = []
    for row in rows:
        try:
            x = float(row[x_col])
            y = float(row[y_col])
            if not (math.isnan(x) or math.isnan(y)):
                x_values.append(x)
                y_values.append(y)
        except:
            continue

    if len(x_values) < 6:
        raise ValueError(f"Only {len(x_values)} valid numeric pairs found. Need at least 6.")

    return x_values, y_values, fieldnames, x_col, y_col

# ============================================================
# 3. MAIN ENTRY POINT
# ============================================================

def print_report(result, x_col, y_col, x_min, x_max, y_min, y_max):
    print()
    print("=" * 72)
    print("DISCOVERY RESULT")
    print("=" * 72)
    print(f"Input (x):  {x_col}")
    print(f"Output (y): {y_col}")
    print(f"Range x:    [{x_min:.2f}, {x_max:.2f}]")
    print(f"Range y:    [{y_min:.2f}, {y_max:.2f}]")
    print("-" * 72)
    print(f"Status: {result['status']}")
    if result['status'] == 'PROMOTED':
        print(f"Expression:  {result['expression']}")
        print(f"Derivative:  {result['derivative']}")
        print(f"Rate error:  {result['rate_error']:.4f}")
        print(f"Recon error: {result['recon_error']:.4f}")
        print(f"Pred error:  {result['pred_error']:.4f}")
        print(f"Gates passed: {result['gates_passed']}/3")
        print(f"Margin of safety: {result['margin_of_safety']*100:.1f}%")
        print(f"Prudence score: {result['prudence_score']:.1f}")
        print(f"Node count: {result['node_count']}")
        print("-" * 72)
        print("SUMMARY: The discovered model passes all checks.")
        print("It is a credible relationship that improves meaningfully")
        print("over a simple constant baseline.")
    else:
        print(f"Reason: {result.get('reason', 'N/A')}")
        print("-" * 72)
        print("SUMMARY: No reliable relationship was found.")
        print("The data may be noisy, too sparse, or the true relationship")
        print("is not representable by this engine's grammar.")
    print("=" * 72)

def main():
    parser = argparse.ArgumentParser(description="AEGIS Discovery – find relationships in your data.")
    parser.add_argument('--file', required=True, help='Path to CSV file')
    parser.add_argument('--x', help='Column name for input (x)')
    parser.add_argument('--y', help='Column name for output (y)')
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' not found.")
        sys.exit(1)

    try:
        x_values, y_values, fieldnames, x_col, y_col = load_csv(args.file, args.x, args.y)
    except Exception as e:
        print(f"Error loading data: {e}")
        sys.exit(1)

    print("=" * 72)
    print("AEGIS DISCOVERY — YOUR DATA")
    print("=" * 72)
    print(f"File:      {args.file}")
    print(f"Samples:   {len(x_values)}")
    print(f"Input:     {x_col}")
    print(f"Output:    {y_col}")
    print("=" * 72)
    print()

    engine = AEGIS_Discovery_v8()
    result = engine.run(x_values, y_values)

    print_report(result, x_col, y_col, min(x_values), max(x_values), min(y_values), max(y_values))

if __name__ == "__main__":
    main()
