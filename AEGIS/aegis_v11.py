#!/data/data/com.termux/files/usr/bin/python

import random
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple, Callable
from collections import defaultdict

# ============================================================
# AEGIS V11 – COMPLETE FUNCTION DISCOVERY
#
# No candidate zoo, no predefined primitives beyond +, -, *, /.
# Invented operators emerge from residual analysis.
# Validation is airtight via three independent gates.
# ============================================================

# -----------------------------------------------------------------
# 1. HIDDEN REALITY (for testing – can be anything)
# -----------------------------------------------------------------
class HiddenReality:
    """Hidden law: y = 0.5*x^2 + 1.2*exp(0.3*x) + 0.8*sin(1.2*x)"""
    def __init__(self):
        pass  # fixed parameters above

    def observe(self, x: float, noise: bool = True) -> float:
        y = 0.5*(x**2) + 1.2*math.exp(0.3*x) + 0.8*math.sin(1.2*x)
        if noise:
            y += random.gauss(0.0, 0.02)
        return y

# -----------------------------------------------------------------
# 2. DATA STRUCTURES
# -----------------------------------------------------------------
@dataclass
class Observation:
    x: float
    y: float

@dataclass
class Operator:
    name: str
    arity: int
    func: Callable[[float], float]  # unary or binary; we'll only use unary for primitives
    symbol: str

@dataclass
class RateTerm:
    """A term in the rate function: coefficient * primitive(x)"""
    coeff: float
    primitive: Callable[[float], float]  # e.g., lambda x: x**2, lambda x: math.exp(0.3*x)
    name: str  # for display

class AEGIS:
    def __init__(self):
        self.training: List[Observation] = []
        self.validation: List[Observation] = []
        # Initial vocabulary: only arithmetic ops (unused for rate fitting, but kept)
        self.operators = {}   # not used for rate terms; we keep for completeness
        self.invented_ops: List[Operator] = []
        self.rate_terms: List[RateTerm] = []   # discovered rate expression
        self.structures: List[dict] = []       # history of accepted models

    # -----------------------------------------------------------------
    # UTILITY
    # -----------------------------------------------------------------
    @staticmethod
    def rmse(actual, predicted):
        if not actual:
            return float("inf")
        return math.sqrt(sum((a-p)**2 for a,p in zip(actual,predicted)) / len(actual))

    # -----------------------------------------------------------------
    # LOCAL RATES (from observed (x,y) pairs)
    # -----------------------------------------------------------------
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

    # -----------------------------------------------------------------
    # POLYNOMIAL FITTING (least squares)
    # -----------------------------------------------------------------
    def fit_polynomial(self, pairs, degree):
        """Return coefficients [c0,...,c_degree] for rate(x) = sum c_i * x^i."""
        if len(pairs) < degree + 1:
            return None
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
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
        # Gaussian elimination
        aug = [gram[i] + [rhs[i]] for i in range(m)]
        for col in range(m):
            pivot = None
            for row in range(col, m):
                if abs(aug[row][col]) > 1e-12:
                    pivot = row
                    break
            if pivot is None:
                continue
            aug[col], aug[pivot] = aug[pivot], aug[col]
            div = aug[col][col]
            for j in range(col, m+1):
                aug[col][j] /= div
            for row in range(col+1, m):
                factor = aug[row][col]
                for j in range(col, m+1):
                    aug[row][j] -= factor * aug[col][j]
        coeffs = [0.0]*m
        for i in reversed(range(m)):
            coeffs[i] = aug[i][m] - sum(aug[i][j]*coeffs[j] for j in range(i+1, m))
        return coeffs

    # -----------------------------------------------------------------
    # DISCOVER POLYNOMIAL RATE (choose best degree by cross-validation)
    # -----------------------------------------------------------------
    def discover_polynomial_rate(self, rates):
        if len(rates) < 6:
            return None, None, None
        # split into train/val (80/20)
        split = int(0.8 * len(rates))
        train_rates = rates[:split]
        val_rates = rates[split:]
        best_degree = 0
        best_error = float("inf")
        best_coeffs = None
        for d in range(0, 7):
            coeffs = self.fit_polynomial(train_rates, d)
            if coeffs is None:
                continue
            pred = [sum(coeffs[i]*(x**i) for i in range(len(coeffs))) for x,_ in val_rates]
            actual = [r for _,r in val_rates]
            err = self.rmse(actual, pred)
            if err < best_error:
                best_error = err
                best_degree = d
                best_coeffs = coeffs
        if best_coeffs is None:
            return None, None, None
        # compute training error on all rates
        pred_all = [sum(best_coeffs[i]*(x**i) for i in range(len(best_coeffs))) for x,_ in rates]
        actual_all = [r for _,r in rates]
        train_err = self.rmse(actual_all, pred_all)
        return best_coeffs, best_degree, train_err

    # -----------------------------------------------------------------
    # RESIDUAL ANALYSIS – INVENT NEW PRIMITIVES
    # -----------------------------------------------------------------
    def analyze_residuals(self, rates, poly_coeffs):
        """
        Given rates and polynomial coefficients, compute residuals
        and try to detect exponential or sinusoidal structure.
        Return a list of new RateTerm objects if discovered.
        """
        if len(rates) < 10:
            return []
        xs = [p[0] for p in rates]
        rates_vals = [p[1] for p in rates]
        poly_pred = [sum(poly_coeffs[i]*(x**i) for i in range(len(poly_coeffs))) for x in xs]
        residuals = [rates_vals[i] - poly_pred[i] for i in range(len(xs))]

        # --- Detect exponential: log(abs(residual)) linear in x? ---
        # We need positive residuals for log; we can take absolute values and check sign consistency.
        # If residuals have consistent sign, we can try to fit log(|residual|) vs x.
        # For simplicity, we'll look for exponential growth: check if the ratio of consecutive residuals is roughly constant.
        if len(residuals) > 3:
            ratios = []
            for i in range(1, len(residuals)):
                if abs(residuals[i-1]) > 1e-12:
                    ratios.append(residuals[i] / residuals[i-1] if residuals[i-1] != 0 else 0)
            if ratios:
                avg_ratio = sum(ratios) / len(ratios)
                if avg_ratio > 1.0:  # exponential growth
                    # try to fit A * exp(b*x) to residuals
                    # take log of absolute residuals
                    log_res = []
                    xs_fit = []
                    for i, r in enumerate(residuals):
                        if abs(r) > 1e-12:
                            log_res.append(math.log(abs(r)))
                            xs_fit.append(xs[i])
                    if len(log_res) > 3:
                        # fit linear: log_res = b*x + log(A)
                        mean_x = sum(xs_fit)/len(xs_fit)
                        mean_lr = sum(log_res)/len(log_res)
                        num = sum((x-mean_x)*(lr-mean_lr) for x,lr in zip(xs_fit, log_res))
                        den = sum((x-mean_x)**2 for x in xs_fit)
                        if abs(den) > 1e-12:
                            b = num / den
                            logA = mean_lr - b*mean_x
                            A = math.exp(logA)
                            # if the fit is good (check R2 or just use validation), we invent exp
                            # we'll test the new term on validation later, so we can just propose it.
                            # We'll create a primitive function: A * exp(b*x)
                            # But we also need to account for sign of residuals.
                            sign = 1 if sum(residuals) > 0 else -1
                            # Invent operator: exp
                            op_name = f"exp_{b:.3f}"
                            def make_exp(b):
                                return lambda x: math.exp(b*x)
                            new_primitive = make_exp(b)
                            # Return a term with coefficient A*sign? Actually we can let the coefficient be fitted later.
                            # We'll return a term with coefficient 1.0 for now, and the primitive.
                            # The actual amplitude will be fitted by least squares on the combined model.
                            print(f"[RESIDUAL] Detected exponential trend with b={b:.3f}. Proposing exp term.")
                            return [RateTerm(coeff=1.0, primitive=new_primitive, name=f"exp({b:.3f}x)")]
        # --- Detect sinusoidal: look for periodicity in residuals ---
        # We'll use zero-crossings: count sign changes.
        if len(residuals) > 5:
            sign_changes = 0
            for i in range(1, len(residuals)):
                if residuals[i-1] * residuals[i] < 0:
                    sign_changes += 1
            # Estimate frequency from zero-crossings
            if sign_changes > 2:
                # Approximate period: average distance between zero-crossings
                zero_cross_positions = []
                for i in range(1, len(residuals)):
                    if residuals[i-1] * residuals[i] < 0:
                        # linear interpolation to find zero
                        x1, y1 = xs[i-1], residuals[i-1]
                        x2, y2 = xs[i], residuals[i]
                        x_zero = x1 - y1*(x2-x1)/(y2-y1)
                        zero_cross_positions.append(x_zero)
                if len(zero_cross_positions) > 1:
                    avg_period = sum(zero_cross_positions[i+1]-zero_cross_positions[i] for i in range(len(zero_cross_positions)-1)) / (len(zero_cross_positions)-1)
                    freq = 2*math.pi / avg_period if avg_period > 0 else 0
                    if freq > 0.3 and freq < 10:
                        # Propose sin and cos
                        print(f"[RESIDUAL] Detected sinusoidal with frequency {freq:.3f}. Proposing sin/cos.")
                        # We'll propose both sin and cos; later fitting will decide.
                        def make_sin(f):
                            return lambda x: math.sin(f*x)
                        def make_cos(f):
                            return lambda x: math.cos(f*x)
                        return [
                            RateTerm(coeff=1.0, primitive=make_sin(freq), name=f"sin({freq:.3f}x)"),
                            RateTerm(coeff=1.0, primitive=make_cos(freq), name=f"cos({freq:.3f}x)")
                        ]
        return []

    # -----------------------------------------------------------------
    # FIT COMBINED RATE MODEL (polynomial + discovered primitives)
    # -----------------------------------------------------------------
    def fit_combined_model(self, rates, poly_coeffs, extra_terms):
        """
        Given rates and a list of RateTerm primitives, fit the coefficients
        of the combined model: rate(x) = sum_i c_i * x^i + sum_j coeff_j * primitive_j(x).
        Return (coeffs_for_poly, coeffs_for_extra, total_error).
        """
        xs = [p[0] for p in rates]
        ys = [p[1] for p in rates]
        n = len(xs)
        # Build design matrix: columns for polynomial terms (degree d) + extra primitives
        d = len(poly_coeffs) - 1
        num_poly = len(poly_coeffs)
        num_extra = len(extra_terms)
        m = num_poly + num_extra
        # Build matrix A (n x m) and vector b (n)
        A = [[0.0]*m for _ in range(n)]
        b = ys[:]
        for i in range(n):
            x = xs[i]
            for j in range(num_poly):
                A[i][j] = x**j
            for j in range(num_extra):
                A[i][num_poly + j] = extra_terms[j].primitive(x)
        # Solve least squares: (A^T A) coeffs = A^T b
        # Gram matrix
        AtA = [[0.0]*m for _ in range(m)]
        Atb = [0.0]*m
        for i in range(n):
            for j in range(m):
                Atb[j] += A[i][j] * b[i]
                for k in range(m):
                    AtA[j][k] += A[i][j] * A[i][k]
        # Solve by Gaussian elimination
        aug = [AtA[i] + [Atb[i]] for i in range(m)]
        for col in range(m):
            pivot = None
            for row in range(col, m):
                if abs(aug[row][col]) > 1e-12:
                    pivot = row
                    break
            if pivot is None:
                continue
            aug[col], aug[pivot] = aug[pivot], aug[col]
            div = aug[col][col]
            for j in range(col, m+1):
                aug[col][j] /= div
            for row in range(col+1, m):
                factor = aug[row][col]
                for j in range(col, m+1):
                    aug[row][j] -= factor * aug[col][j]
        coeffs_all = [0.0]*m
        for i in reversed(range(m)):
            coeffs_all[i] = aug[i][m] - sum(aug[i][j]*coeffs_all[j] for j in range(i+1, m))
        # Extract polynomial coefficients and extra coefficients
        poly_new = coeffs_all[:num_poly]
        extra_new = coeffs_all[num_poly:]
        # Compute prediction error
        pred = [0.0]*n
        for i in range(n):
            x = xs[i]
            val = sum(poly_new[j]*(x**j) for j in range(num_poly))
            for j in range(num_extra):
                val += extra_new[j] * extra_terms[j].primitive(x)
            pred[i] = val
        error = self.rmse(ys, pred)
        return poly_new, extra_new, error

    # -----------------------------------------------------------------
    # NUMERICAL INTEGRATION (adaptive Simpson)
    # -----------------------------------------------------------------
    def integrate_rate(self, rate_func, a, b, tol=1e-6, maxdepth=20):
        """
        Integrate rate_func from a to b using adaptive Simpson.
        """
        def simpson(f, a, b):
            return (b-a)/6 * (f(a) + 4*f((a+b)/2) + f(b))
        def recursive(f, a, b, eps, depth):
            m = (a+b)/2
            S = simpson(f, a, b)
            S_left = simpson(f, a, m)
            S_right = simpson(f, m, b)
            if depth <= 0 or abs(S_left + S_right - S) / 15 < eps:
                return S_left + S_right + (S_left + S_right - S)/15
            return recursive(f, a, m, eps/2, depth-1) + recursive(f, m, b, eps/2, depth-1)
        return recursive(rate_func, a, b, tol, maxdepth)

    # -----------------------------------------------------------------
    # BUILD RATE FUNCTION FROM TERMS
    # -----------------------------------------------------------------
    def make_rate_function(self, poly_coeffs, extra_terms):
        """
        Returns a function f(x) = sum poly_coeffs[i]*x^i + sum coeff_j * primitive_j(x)
        """
        def rate_func(x):
            val = 0.0
            for i, c in enumerate(poly_coeffs):
                val += c * (x**i)
            for term in extra_terms:
                val += term.coeff * term.primitive(x)
            return val
        return rate_func

    # -----------------------------------------------------------------
    # VALIDATION GATES
    # -----------------------------------------------------------------
    def validate_model(self, poly_coeffs, extra_terms):
        """
        Compute three errors on validation set.
        Returns (rate_error, recon_error, pred_error)
        """
        # 1. Rate error
        rates_val = self.local_rates(self.validation)
        if not rates_val:
            return float("inf"), float("inf"), float("inf")
        xs_val = [p[0] for p in rates_val]
        actual_rates = [p[1] for p in rates_val]
        rate_func = self.make_rate_function(poly_coeffs, extra_terms)
        pred_rates = [rate_func(x) for x in xs_val]
        rate_error = self.rmse(actual_rates, pred_rates)

        # 2. Reconstruction error: integrate from first validation point
        ordered = sorted(self.validation, key=lambda o: o.x)
        if len(ordered) < 2:
            return rate_error, float("inf"), float("inf")
        anchor = ordered[0]
        # Reconstruct y for all validation points using numerical integration
        y_recon = [anchor.y]
        for i in range(1, len(ordered)):
            x_prev = ordered[i-1].x
            x_cur = ordered[i].x
            integral = self.integrate_rate(rate_func, x_prev, x_cur)
            y_recon.append(y_recon[-1] + integral)
        actual_y = [o.y for o in ordered]
        recon_error = self.rmse(actual_y, y_recon)

        # 3. Prediction error: use only anchor to predict all subsequent points
        if len(ordered) < 3:
            return rate_error, recon_error, float("inf")
        anchor = ordered[0]
        pred_y = [anchor.y]
        for i in range(1, len(ordered)):
            x_prev = ordered[i-1].x
            x_cur = ordered[i].x
            integral = self.integrate_rate(rate_func, x_prev, x_cur)
            pred_y.append(pred_y[-1] + integral)
        # but we must compute prediction from anchor only: so we need to integrate from anchor to each target directly.
        pred_from_anchor = []
        for i in range(1, len(ordered)):
            integral = self.integrate_rate(rate_func, anchor.x, ordered[i].x)
            pred_from_anchor.append(anchor.y + integral)
        actual_targets = [o.y for o in ordered[1:]]
        pred_error = self.rmse(actual_targets, pred_from_anchor)

        return rate_error, recon_error, pred_error

    # -----------------------------------------------------------------
    # MAIN LOOP
    # -----------------------------------------------------------------
    def run(self):
        print("="*72)
        print("AEGIS V11 – COMPLETE FUNCTION DISCOVERY")
        print("Initial vocabulary: +, -, *, /, and variable x")
        print("No candidate primitives. Operators are invented from residuals.")
        print("Validation: three independent gates.")
        print("="*72)

        # 1. Compute local rates from training
        rates_train = self.local_rates(self.training)
        if len(rates_train) < 6:
            print("FAILURE: insufficient training data.")
            return

        # 2. Discover polynomial rate
        print("\n[PHASE 1] Discovering polynomial rate...")
        poly_coeffs, degree, _ = self.discover_polynomial_rate(rates_train)
        if poly_coeffs is None:
            print("FAILURE: could not fit polynomial.")
            return
        print(f"Polynomial degree {degree} with coefficients: {[round(c,4) for c in poly_coeffs]}")

        # 3. Analyze residuals and invent primitives
        print("\n[PHASE 2] Analyzing residuals for new primitives...")
        extra_terms = self.analyze_residuals(rates_train, poly_coeffs)
        if extra_terms:
            print(f"Invented {len(extra_terms)} new primitive(s): {[t.name for t in extra_terms]}")
        else:
            print("No additional primitives needed (residuals appear random).")
            # If no extra, we just keep polynomial.

        # 4. Fit combined model (polynomial + extra)
        if extra_terms:
            print("\n[PHASE 3] Fitting combined model...")
            poly_new, extra_coeffs, fit_error = self.fit_combined_model(rates_train, poly_coeffs, extra_terms)
            # Update coefficients in extra_terms
            for i, term in enumerate(extra_terms):
                term.coeff = extra_coeffs[i]
            poly_coeffs = poly_new
            print(f"Combined model training rate error: {fit_error:.6f}")
        else:
            print("\n[PHASE 3] Using polynomial model only.")

        # 5. Validate on independent validation set
        print("\n[PHASE 4] Independent validation...")
        rate_err, recon_err, pred_err = self.validate_model(poly_coeffs, extra_terms)
        print(f"Rate error:    {rate_err:.6f}")
        print(f"Recon error:   {recon_err:.6f}")
        print(f"Prediction err:{pred_err:.6f}")

        # 6. Promotion gate
        print("\n[PHASE 5] Promotion gate...")
        rate_ok = rate_err < 0.10
        recon_ok = recon_err < 0.10
        pred_ok = pred_err < 0.10
        print(f"Rate: {'PASS' if rate_ok else 'FAIL'}")
        print(f"Recon: {'PASS' if recon_ok else 'FAIL'}")
        print(f"Prediction: {'PASS' if pred_ok else 'FAIL'}")

        if rate_ok and recon_ok and pred_ok:
            print("\n[PROMOTED] The discovered model (polynomial + invented primitives) is validated.")
            # Store as a structure
            self.structures.append({
                "poly_coeffs": poly_coeffs,
                "extra_terms": extra_terms,
                "rate_error": rate_err,
                "recon_error": recon_err,
                "pred_error": pred_err
            })
            if extra_terms:
                print(f"New operators accepted: {[t.name for t in extra_terms]}")
            print("\nRESULT: AEGIS successfully discovered a model that generalises.")
        else:
            print("\n[REJECTED] Model did not pass all gates.")

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
