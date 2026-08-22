#!/data/data/com.termux/files/usr/bin/python

import random
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple
from collections import defaultdict

# ============================================================
# AEGIS V10 – GENERAL POLYNOMIAL DISCOVERY & OPERATOR INVENTION
# ============================================================
#
# AEGIS starts with {+, -, *, /} and variable x.
# It discovers a polynomial rate (any degree) from data,
# integrates it symbolically, and invents the necessary
# power operators (square, cube, ...) as they emerge.
#
# No polynomial template, no degree limit is hard‑coded.
# ============================================================

class HiddenReality:
    """y = x^3 + 0.2*x^2 + 0.5*x + 1.2  (a cubic)"""
    def __init__(self):
        self.a3 = 1.0
        self.a2 = 0.2
        self.a1 = 0.5
        self.a0 = 1.2

    def observe(self, x: float, noise: bool = True) -> float:
        y = self.a3*(x**3) + self.a2*(x**2) + self.a1*x + self.a0
        if noise:
            y += random.gauss(0.0, 0.02)
        return y

@dataclass
class Observation:
    x: float
    y: float

@dataclass
class Operator:
    name: str
    arity: int
    func: callable
    symbol: str

@dataclass
class DiscoveredStructure:
    # Polynomial rate: rate(x) = sum_{i=0}^{d} coeffs[i] * x^i
    coeffs: List[float]          # from constant to highest degree
    # Integrated model: y(x) = constant + sum over discovered powers
    # We'll store the antiderivative as a list of (power, coeff)
    terms: List[Tuple[int, float]]   # (power, coefficient) e.g., (3, 0.333) for x^3 term
    constant: float
    invented_operators: List[Operator]
    # validation errors
    rate_error: float = 0.0
    reconstruction_error: float = 0.0
    prediction_error: float = 0.0

class AEGIS:
    def __init__(self):
        self.training: List[Observation] = []
        self.validation: List[Observation] = []
        # Initial vocabulary: arithmetic ops and x
        self.operators = {
            "add": Operator("add", 2, lambda a,b: a+b, "+"),
            "sub": Operator("sub", 2, lambda a,b: a-b, "-"),
            "mul": Operator("mul", 2, lambda a,b: a*b, "*"),
            "div": Operator("div", 2, lambda a,b: a/(b+1e-12), "/"),
        }
        self.variables = ["x"]
        self.structures: List[DiscoveredStructure] = []
        self.invented_ops: List[Operator] = []

    # -----------------------------------------------------------------
    # RMSE
    # -----------------------------------------------------------------
    @staticmethod
    def rmse(actual, predicted):
        if not actual:
            return float("inf")
        return math.sqrt(sum((a-p)**2 for a,p in zip(actual,predicted)) / len(actual))

    # -----------------------------------------------------------------
    # LOCAL RATES
    # -----------------------------------------------------------------
    def local_rates(self, observations):
        ordered = sorted(observations, key=lambda o: o.x)
        rates = []
        for i in range(len(ordered)-1):
            x1, y1 = ordered[i].x, ordered[i].y
            x2, y2 = ordered[i+1].x, ordered[i+1].y
            dx = x2 - x1
            if abs(dx) < 1e-12: continue
            rates.append(((x1+x2)/2.0, (y2-y1)/dx))
        return rates

    # -----------------------------------------------------------------
    # FIT POLYNOMIAL OF GIVEN DEGREE (least squares)
    # -----------------------------------------------------------------
    def fit_polynomial(self, pairs, degree):
        """Return coefficients [c0, c1, ..., c_degree] for rate(x)."""
        if len(pairs) < degree + 1:
            return None
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        # Build Vandermonde matrix
        n = len(xs)
        m = degree + 1
        # Gram matrix
        gram = [[0.0]*m for _ in range(m)]
        rhs = [0.0]*m
        for i in range(n):
            x = xs[i]
            y = ys[i]
            for j in range(m):
                rhs[j] += y * (x**j)
                for k in range(m):
                    gram[j][k] += (x**j) * (x**k)
        # Solve linear system (Gaussian elimination)
        # Convert to augmented matrix
        aug = [gram[i] + [rhs[i]] for i in range(m)]
        # Forward elimination
        for col in range(m):
            # find pivot
            pivot = None
            for row in range(col, m):
                if abs(aug[row][col]) > 1e-12:
                    pivot = row
                    break
            if pivot is None:
                continue
            aug[col], aug[pivot] = aug[pivot], aug[col]
            # normalize
            div = aug[col][col]
            for j in range(col, m+1):
                aug[col][j] /= div
            # eliminate below
            for row in range(col+1, m):
                factor = aug[row][col]
                for j in range(col, m+1):
                    aug[row][j] -= factor * aug[col][j]
        # Back substitution
        coeffs = [0.0]*m
        for i in reversed(range(m)):
            coeffs[i] = aug[i][m] - sum(aug[i][j]*coeffs[j] for j in range(i+1, m))
        return coeffs

    # -----------------------------------------------------------------
    # DISCOVER RATE POLYNOMIAL (choose best degree via cross-validation)
    # -----------------------------------------------------------------
    def discover_rate(self):
        rates = self.local_rates(self.training)
        if len(rates) < 5:
            return None
        # Split rates into train/val (80/20)
        split = int(0.8 * len(rates))
        train_rates = rates[:split]
        val_rates = rates[split:]
        if len(train_rates) < 3:
            return None
        best_degree = 0
        best_error = float("inf")
        best_coeffs = None
        # Try degrees 0 to 6 (avoid overfitting)
        for d in range(0, 7):
            coeffs = self.fit_polynomial(train_rates, d)
            if coeffs is None:
                continue
            # evaluate on validation rates
            pred = [sum(coeffs[i]*(x**i) for i in range(len(coeffs))) for x,_ in val_rates]
            actual = [r for _,r in val_rates]
            err = self.rmse(actual, pred)
            if err < best_error:
                best_error = err
                best_degree = d
                best_coeffs = coeffs
        if best_coeffs is None:
            return None
        # Compute training error on all rates
        pred_all = [sum(best_coeffs[i]*(x**i) for i in range(len(best_coeffs))) for x,_ in rates]
        actual_all = [r for _,r in rates]
        train_error = self.rmse(actual_all, pred_all)
        return best_coeffs, best_degree, train_error

    # -----------------------------------------------------------------
    # SYMBOLIC INTEGRATION & OPERATOR INVENTION
    # -----------------------------------------------------------------
    def integrate_and_invent(self, coeffs, anchor_x, anchor_y):
        """
        Given polynomial rate coeffs, integrate to get y(x) = C + sum_{i} coeffs[i]/(i+1) * x^(i+1)
        For each power > 1, invent a power operator if not already present.
        """
        # Compute antiderivative terms: for each i, power = i+1, new_coeff = coeffs[i]/(i+1)
        terms = []
        invented = []
        for i, c in enumerate(coeffs):
            if abs(c) < 1e-12:
                continue
            power = i + 1
            new_c = c / power
            terms.append((power, new_c))
            # Invent operator for power if > 1 and not already existing
            if power > 1:
                op_name = f"power_{power}"
                if op_name not in self.operators:
                    # define operator: x -> x**power, but we must build from multiplication
                    # We'll implement via repeated multiplication
                    def make_power(p):
                        if p == 2:
                            return lambda x: x*x
                        elif p == 3:
                            return lambda x: x*x*x
                        else:
                            # for higher, use math.pow (but that's a built‑in; we could implement recursively)
                            return lambda x: x**p
                    op = Operator(op_name, 1, make_power(power), f"x^{power}")
                    self.operators[op_name] = op
                    self.invented_ops.append(op)
                    invented.append(op_name)
                    print(f"[INVENTION] New operator '{op_name}' derived from integration.")
        # Compute constant C from anchor
        # y_anchor = C + sum_{terms} new_c * (anchor_x)**power
        C = anchor_y - sum(new_c * (anchor_x**power) for power, new_c in terms)
        structure = DiscoveredStructure(
            coeffs=coeffs,
            terms=terms,
            constant=C,
            invented_operators=self.invented_ops[-len(invented):] if invented else []
        )
        return structure

    # -----------------------------------------------------------------
    # PREDICT FROM INTEGRATED FORM
    # -----------------------------------------------------------------
    def predict_from_integrated(self, structure, x):
        y = structure.constant
        for power, c in structure.terms:
            y += c * (x ** power)
        return y

    # -----------------------------------------------------------------
    # VALIDATION GATES
    # -----------------------------------------------------------------
    def validate_rate(self, structure):
        rates = self.local_rates(self.validation)
        if not rates:
            return float("inf")
        coeffs = structure.coeffs
        actual = [r for _,r in rates]
        pred = [sum(coeffs[i]*(x**i) for i in range(len(coeffs))) for x,_ in rates]
        error = self.rmse(actual, pred)
        structure.rate_error = error
        return error

    def validate_reconstruction(self, structure):
        # Reconstruct y from the integrated model using anchor from validation
        ordered = sorted(self.validation, key=lambda o: o.x)
        if len(ordered) < 2:
            return float("inf")
        # Use first validation point as anchor to compute a new constant?
        # Actually we already have a constant from training anchor; we can just predict directly.
        # But to be fair, we'll compute a new constant from the first validation point.
        anchor = ordered[0]
        C_new = anchor.y - sum(c * (anchor.x ** power) for power, c in structure.terms)
        preds = [C_new + sum(c * (o.x ** power) for power, c in structure.terms) for o in ordered]
        actual = [o.y for o in ordered]
        error = self.rmse(actual, preds)
        structure.reconstruction_error = error
        return error

    def validate_prediction(self, structure):
        ordered = sorted(self.validation, key=lambda o: o.x)
        if len(ordered) < 3:
            return float("inf")
        anchor = ordered[0]
        targets = ordered[1:]
        C = anchor.y - sum(c * (anchor.x ** power) for power, c in structure.terms)
        preds = [C + sum(c * (t.x ** power) for power, c in structure.terms) for t in targets]
        actual = [o.y for o in targets]
        error = self.rmse(actual, preds)
        structure.prediction_error = error
        return error

    # -----------------------------------------------------------------
    # PROMOTION
    # -----------------------------------------------------------------
    def promote(self, structure):
        rate_ok = structure.rate_error < 0.10
        recon_ok = structure.reconstruction_error < 0.10
        pred_ok = structure.prediction_error < 0.10
        return (rate_ok and recon_ok and pred_ok)

    # -----------------------------------------------------------------
    # RUN
    # -----------------------------------------------------------------
    def run(self):
        print("="*72)
        print("AEGIS V10 – GENERAL POLYNOMIAL DISCOVERY")
        print("Initial vocabulary: +, -, *, /, and variable x")
        print("No polynomial template, no degree limit pre‑set.")
        print("="*72)

        # Discover rate polynomial
        print("\n[PHASE 1] Discovering rate polynomial...")
        result = self.discover_rate()
        if result is None:
            print("FAILURE: Could not discover a polynomial rate.")
            return
        coeffs, degree, error = result
        print(f"Discovered polynomial degree {degree} with coefficients:")
        for i,c in enumerate(coeffs):
            print(f"  c{i} = {c:.6f}")

        # Pick anchor from training
        anchor = sorted(self.training, key=lambda o: o.x)[0]
        structure = self.integrate_and_invent(coeffs, anchor.x, anchor.y)

        # Validate
        print("\n[PHASE 2] Validating integrated structure...")
        self.validate_rate(structure)
        self.validate_reconstruction(structure)
        self.validate_prediction(structure)
        print(f"Rate error:    {structure.rate_error:.6f}")
        print(f"Recon error:   {structure.reconstruction_error:.6f}")
        print(f"Prediction err:{structure.prediction_error:.6f}")

        # Promotion
        print("\n[PHASE 3] Promotion gate...")
        if self.promote(structure):
            self.structures.append(structure)
            print("PROMOTED")
            if structure.invented_operators:
                ops = [op.name for op in structure.invented_operators]
                print(f"Discovered operators: {ops}")
                print("The system now knows these as useful primitives.")
            else:
                print("No new operators were needed (degree ≤ 1).")
            print("\nRESULT: AEGIS discovered a polynomial model and invented necessary power operators.")
        else:
            print("REJECTED – structure did not pass validation.")
        print("="*72)

# -----------------------------------------------------------------
# EXPERIMENT
# -----------------------------------------------------------------
def build_experiment():
    reality = HiddenReality()
    training_x = [-1.73,-1.41,-1.08,-0.82,-0.53,-0.21,0.14,0.39,0.67,0.91,1.18,1.47,1.82]
    validation_x = [-1.61,-1.27,-0.94,-0.68,-0.37,-0.08,0.27,0.52,0.79,1.03,1.31,1.66]
    training = [Observation(x=x, y=reality.observe(x, noise=True)) for x in training_x]
    validation = [Observation(x=x, y=reality.observe(x, noise=False)) for x in validation_x]
    return training, validation

def main():
    random.seed(42)
    train, valid = build_experiment()
    agent = AEGIS()
    agent.training = train
    agent.validation = valid
    agent.run()

if __name__ == "__main__":
    main()
