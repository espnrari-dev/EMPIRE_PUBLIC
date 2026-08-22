#!/data/data/com.termux/files/usr/bin/python

"""
AEGIS Discovery Engine v8 – Prudent & Practical
- Simplicity: penalize complexity, but allow up to 20 nodes
- Margin of safety: need >30% improvement over baseline (not 50%)
- Stability: accept if node count variation < 50% across folds (not 20%)
- Prudence score threshold: >60 (not 80)
- Keeps all other checks (rates, reconstruction, prediction, singularities)
"""

import math
import random
import copy
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class Observation:
    x: float
    y: float

# ============================================================
# NODE REPRESENTATION (same as V7)
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

# ============================================================
# EVALUATION (same as V7)
# ============================================================

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

# ============================================================
# SYMBOLIC DERIVATIVE (same as V7)
# ============================================================

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

# ============================================================
# CONSTANT OPTIMIZATION (same as V7)
# ============================================================

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

def rmse_only(node, x_data, y_data):
    try:
        total = sum((evaluate_node(node, x) - y)**2 for x, y in zip(x_data, y_data))
        return math.sqrt(total / len(x_data))
    except:
        return float('inf')

# ============================================================
# GENETIC PROGRAMMING
# ============================================================

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

# ============================================================
# PRUDENCE CHECKS (adjusted thresholds)
# ============================================================

def baseline_rmse(y_data):
    mean_y = sum(y_data) / len(y_data)
    return math.sqrt(sum((y - mean_y)**2 for y in y_data) / len(y_data))

def margin_of_safety(expr_rmse, baseline_rmse):
    if baseline_rmse == 0:
        return float('inf')
    return (baseline_rmse - expr_rmse) / baseline_rmse

def cross_validate_structure(x_data, y_data, model_node, n_folds=3):
    """Check structure stability across folds with relaxed tolerance."""
    paired = sorted(zip(x_data, y_data), key=lambda p: p[0])
    n = len(paired)
    fold_size = n // n_folds
    structures = []
    for i in range(n_folds):
        test = paired[i*fold_size:(i+1)*fold_size]
        train = [p for j, p in enumerate(paired) if j < i*fold_size or j >= (i+1)*fold_size]
        x_train, y_train = zip(*train)
        gp = GeneticProgram(population_size=150, generations=40, max_depth=5)  # faster folds
        best = gp.evolve(list(x_train), list(y_train))
        structures.append(best.simplify().node_count())
    # Accept if node count variation < 50% of average
    avg_nodes = sum(structures) / len(structures)
    if max(structures) - min(structures) > 0.5 * avg_nodes:
        return False
    return True

# ============================================================
# MAIN DISCOVERY ENGINE
# ============================================================

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

        # Check singularities
        for x in [o.x for o in val_obs] + [0.0, 1.0, -1.0]:
            try:
                evaluate_node(expr_node, x)
            except:
                return None

        # Rate gate
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

        # Reconstruction gate
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

        # Prediction gate
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

        # Margin of safety
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

        # Validate
        val_res = self.validate_candidate(best_expr, x_values, y_values)
        if val_res is None:
            return {"status": "REJECTED", "reason": "Singularities or validation failed."}

        # Margin of safety (relaxed)
        if not val_res['mos_ok']:
            return {
                "status": "REJECTED",
                "reason": f"Margin of safety too low ({(val_res['margin_of_safety']*100):.1f}% improvement over baseline, need >30%)."
            }

        # Cross-validation stability (relaxed)
        stable = cross_validate_structure(x_train, y_train, best_expr, n_folds=3)
        if not stable:
            return {"status": "REJECTED", "reason": "Discovered structure unstable across data folds."}

        # Complexity limit
        if best_expr.node_count() > 20:
            return {"status": "REJECTED", "reason": f"Expression too complex (nodes: {best_expr.node_count()})."}

        # Prudence score (relaxed threshold)
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

        # Promote
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
# DEMONSTRATION
# ============================================================

def main():
    random.seed(42)
    print("="*72)
    print("AEGIS DISCOVERY ENGINE v8 – Prudent & Practical")
    print("="*72)
    print()

    # Quadratic data
    print("[1] Quadratic data (y = x² + 0.35x + noise)")
    x_vals = [-1.73, -1.41, -1.08, -0.82, -0.53, -0.21,
              0.14, 0.39, 0.67, 0.91, 1.18, 1.47, 1.82]
    y_vals = [(x*x) + 0.35*x + random.gauss(0.0, 0.01) for x in x_vals]
    engine = AEGIS_Discovery_v8()
    result = engine.run(x_vals, y_vals)
    print(f"  Status: {result['status']}")
    if result['status'] == 'PROMOTED':
        print(f"  Expression: {result['expression']}")
        print(f"  Prudence score: {result['prudence_score']:.1f}")
        print(f"  Margin of safety: {result['margin_of_safety']*100:.1f}%")
    else:
        print(f"  Reason: {result.get('reason', 'N/A')}")
    print()

    # Linear data
    print("[2] Linear data (y = 3x + 1)")
    x_linear = [-3, -2, -1, 0, 1, 2, 3, 4, 5]
    y_linear = [3*x + 1 for x in x_linear]
    engine = AEGIS_Discovery_v8()
    result = engine.run(x_linear, y_linear)
    print(f"  Status: {result['status']}")
    if result['status'] == 'PROMOTED':
        print(f"  Expression: {result['expression']}")
        print(f"  Prudence score: {result['prudence_score']:.1f}")
    else:
        print(f"  Reason: {result.get('reason', 'N/A')}")
    print()

    # Exponential data
    print("[3] Exponential data (y = 2*exp(0.5*x) + 1)")
    x_exp = [i/2.0 for i in range(-4, 6)]
    y_exp = [2*math.exp(0.5*x) + 1 + random.gauss(0.0, 0.02) for x in x_exp]
    engine = AEGIS_Discovery_v8()
    result = engine.run(x_exp, y_exp)
    print(f"  Status: {result['status']}")
    if result['status'] == 'PROMOTED':
        print(f"  Expression: {result['expression']}")
        print(f"  Prudence score: {result['prudence_score']:.1f}")
    else:
        print(f"  Reason: {result.get('reason', 'N/A')}")
    print()

    # Pure noise
    print("[4] Pure noise")
    random.seed(99)
    x_noise = [i/10.0 for i in range(30)]
    y_noise = [random.gauss(0.0, 1.0) for _ in range(30)]
    engine = AEGIS_Discovery_v8()
    result = engine.run(x_noise, y_noise)
    print(f"  Status: {result['status']}")
    if result['status'] == 'REJECTED':
        print(f"  Reason: {result.get('reason', 'N/A')}")
    print("="*72)

if __name__ == "__main__":
    main()
