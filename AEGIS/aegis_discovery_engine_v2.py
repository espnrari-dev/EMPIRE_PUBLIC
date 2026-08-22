#!/data/data/com.termux/files/usr/bin/python

"""
AEGIS Discovery Engine v2 – True Structure Discovery

This engine does NOT assume the rate is linear.
It tests multiple candidate rate forms:
  - constant: rate(x) = c
  - linear:   rate(x) = a*x + b
  - quadratic: rate(x) = a*x^2 + b*x + c
  - exponential: rate(x) = a*exp(b*x) + c

For each form, it:
  1. Fits the rate to the observed local derivatives.
  2. Integrates the rate to reconstruct the original curve.
  3. Validates against three gates (rate, reconstruction, prediction).
  4. Promotes the best form that passes all gates (or the simplest if multiple pass).

The engine is deterministic, dependency‑free, and self‑certifying.
"""

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple, Callable

# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class Observation:
    x: float
    y: float

@dataclass
class Candidate:
    name: str
    params: List[float]           # coefficients for the rate form
    rate_func: Callable[[float], float]
    integrated_func: Callable[[float, float], float]  # (x, C) -> y
    rate_error: float
    recon_error: float
    pred_error: float
    gates_passed: int
    promoted: bool = False

# ============================================================
# DISCOVERY ENGINE
# ============================================================

class AEGIS_Discovery:
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

    def _local_rates(self, observations: List[Observation]) -> List[Tuple[float, float]]:
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

    # ------------------------------------------------------------
    # CANDIDATE FITTERS (each returns (params, rate_func, integrated_func))
    # ------------------------------------------------------------

    def _fit_constant_rate(self, pairs: List[Tuple[float, float]]) -> Tuple[List[float], Callable, Callable]:
        # rate(x) = c
        ys = [y for _, y in pairs]
        c = sum(ys) / len(ys)
        def rate_func(x): return c
        def integrated_func(x, C): return c * x + C
        return [c], rate_func, integrated_func

    def _fit_linear_rate(self, pairs: List[Tuple[float, float]]) -> Optional[Tuple[List[float], Callable, Callable]]:
        # rate(x) = a*x + b
        if len(pairs) < 3:
            return None
        xs = [x for x, _ in pairs]
        ys = [y for _, y in pairs]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        num = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
        den = sum((x - mean_x) ** 2 for x, _ in pairs)
        if abs(den) < 1e-12:
            return None
        a = num / den
        b = mean_y - a * mean_x
        def rate_func(x): return a * x + b
        def integrated_func(x, C): return (a/2) * x*x + b * x + C
        return [a, b], rate_func, integrated_func

    def _fit_quadratic_rate(self, pairs: List[Tuple[float, float]]) -> Optional[Tuple[List[float], Callable, Callable]]:
        # rate(x) = a*x^2 + b*x + c
        if len(pairs) < 4:
            return None
        xs = [x for x, _ in pairs]
        ys = [y for _, y in pairs]
        # Solve least squares for [a, b, c] in: y = a*x^2 + b*x + c
        n = len(xs)
        Sx = sum(xs)
        Sx2 = sum(x**2 for x in xs)
        Sx3 = sum(x**3 for x in xs)
        Sx4 = sum(x**4 for x in xs)
        Sy = sum(ys)
        Sxy = sum(x*y for x, y in pairs)
        Sx2y = sum(x*x*y for x, y in pairs)
        # Matrix:
        # [ Sx4, Sx3, Sx2 ] [a]   [Sx2y]
        # [ Sx3, Sx2, Sx  ] [b] = [Sxy ]
        # [ Sx2, Sx,  n   ] [c]   [Sy  ]
        det = (Sx4 * (Sx2 * n - Sx * Sx) -
               Sx3 * (Sx3 * n - Sx * Sx2) +
               Sx2 * (Sx3 * Sx - Sx2 * Sx2))
        if abs(det) < 1e-12:
            return None
        a = ((Sx2y * (Sx2 * n - Sx * Sx) -
              Sxy * (Sx3 * n - Sx * Sx2) +
              Sy  * (Sx3 * Sx - Sx2 * Sx2)) / det)
        b = ((Sx4 * (Sxy * n - Sx * Sy) -
              Sx3 * (Sx2y * n - Sx * Sy) +
              Sx2 * (Sx2y * Sx - Sxy * Sx2)) / det)
        c = ((Sx4 * (Sx2 * Sy - Sx * Sxy) -
              Sx3 * (Sx3 * Sy - Sx * Sx2y) +
              Sx2 * (Sx3 * Sxy - Sx2 * Sx2y)) / det)
        def rate_func(x): return a * x*x + b * x + c
        def integrated_func(x, C): return (a/3)*x*x*x + (b/2)*x*x + c*x + C
        return [a, b, c], rate_func, integrated_func

    def _fit_exponential_rate(self, pairs: List[Tuple[float, float]]) -> Optional[Tuple[List[float], Callable, Callable]]:
        # rate(x) = A * exp(B*x) + C
        # We'll fit in log space if possible
        if len(pairs) < 4:
            return None
        # First, try to fit A*exp(B*x) by linearizing: log(rate) = log(A) + B*x
        # We need positive rates for log; take absolute values
        xs = [x for x, _ in pairs]
        ys = [y for _, y in pairs]
        # Use absolute values for log, but keep sign separate.
        # Simple approach: fit to raw data using least squares on log(|y|)
        log_ys = [math.log(abs(y) + 1e-12) for y in ys]
        mean_x = sum(xs) / len(xs)
        mean_log = sum(log_ys) / len(log_ys)
        num = sum((x - mean_x) * (log_y - mean_log) for x, log_y in zip(xs, log_ys))
        den = sum((x - mean_x) ** 2 for x in xs)
        if abs(den) < 1e-12:
            return None
        B = num / den
        log_A = mean_log - B * mean_x
        A = math.exp(log_A)
        # Now fit C as the mean residual: rate - A*exp(B*x)
        pred = [A * math.exp(B * x) for x in xs]
        residuals = [ys[i] - pred[i] for i in range(len(ys))]
        C = sum(residuals) / len(residuals)
        def rate_func(x): return A * math.exp(B * x) + C
        def integrated_func(x, C0):
            if abs(B) < 1e-12:
                return (A + C) * x + C0
            return (A / B) * math.exp(B * x) + C * x + C0
        return [A, B, C], rate_func, integrated_func

    # ------------------------------------------------------------
    # EVALUATE A CANDIDATE
    # ------------------------------------------------------------

    def evaluate_candidate(self, rate_pairs: List[Tuple[float, float]], val_obs: List[Observation],
                           fit_result: Tuple[List[float], Callable, Callable]) -> Optional[Candidate]:
        params, rate_func, integrated_func = fit_result

        # Rate error on training (or validation) – we'll use validation rates
        val_rates = self._local_rates(val_obs)
        if not val_rates:
            return None
        actual = [r for _, r in val_rates]
        predicted = [rate_func(x) for x, _ in val_rates]
        rate_error = self.rmse(actual, predicted)

        # Reconstruction error (integrate from first point)
        ordered = sorted(val_obs, key=lambda o: o.x)
        if len(ordered) < 2:
            return None
        # Choose integration constant so that the curve starts at the first point
        x0 = ordered[0].x
        y0 = ordered[0].y
        C_const = y0 - integrated_func(x0, 0.0)
        recon_pred = [integrated_func(o.x, C_const) for o in ordered]
        recon_actual = [o.y for o in ordered]
        recon_error = self.rmse(recon_actual, recon_pred)

        # Prediction from anchor (first point) to all others
        if len(ordered) < 3:
            pred_error = float("inf")
        else:
            anchor = ordered[0]
            targets = ordered[1:]
            C_const = anchor.y - integrated_func(anchor.x, 0.0)
            preds = [integrated_func(t.x, C_const) for t in targets]
            pred_actual = [t.y for t in targets]
            pred_error = self.rmse(pred_actual, preds)

        gates_passed = 0
        if rate_error < 0.10: gates_passed += 1
        if recon_error < 0.10: gates_passed += 1
        if pred_error < 0.10: gates_passed += 1

        return Candidate(
            name="",
            params=params,
            rate_func=rate_func,
            integrated_func=integrated_func,
            rate_error=rate_error,
            recon_error=recon_error,
            pred_error=pred_error,
            gates_passed=gates_passed,
            promoted=False
        )

    # ------------------------------------------------------------
    # DISCOVERY LOOP
    # ------------------------------------------------------------

    def discover(self) -> List[Candidate]:
        # Split data into training and validation (70/30)
        all_obs = self.training + self.validation
        n = len(all_obs)
        split = int(0.7 * n)
        train = all_obs[:split]
        val = all_obs[split:]

        # Compute local rates on training set
        train_rates = self._local_rates(train)
        if len(train_rates) < 5:
            return []

        candidates = []

        # Try each form
        fits = [
            ("constant", self._fit_constant_rate),
            ("linear", self._fit_linear_rate),
            ("quadratic", self._fit_quadratic_rate),
            ("exponential", self._fit_exponential_rate),
        ]

        for name, fit_func in fits:
            try:
                fit_result = fit_func(train_rates)
                if fit_result is None:
                    continue
                cand = self.evaluate_candidate(train_rates, val, fit_result)
                if cand is None:
                    continue
                cand.name = name
                candidates.append(cand)
            except Exception:
                continue

        # Promote those that passed all gates
        for c in candidates:
            if c.gates_passed == 3:
                c.promoted = True

        return candidates

    def run(self, x_values: List[float], y_values: List[float]) -> Dict:
        if len(x_values) != len(y_values) or len(x_values) < 6:
            return {"status": "INSUFFICIENT_DATA", "candidates": []}

        obs = [Observation(x=x, y=y) for x, y in zip(x_values, y_values)]
        self.receive(obs)
        candidates = self.discover()

        promoted = [c for c in candidates if c.promoted]
        if promoted:
            best = min(promoted, key=lambda c: c.rate_error + c.recon_error + c.pred_error)
            return {
                "status": "PROMOTED",
                "best_shape": best.name,
                "params": best.params,
                "rate_error": best.rate_error,
                "recon_error": best.recon_error,
                "pred_error": best.pred_error,
                "gates_passed": best.gates_passed,
                "all_candidates": [(c.name, c.gates_passed, c.rate_error, c.recon_error, c.pred_error) for c in candidates]
            }
        else:
            return {
                "status": "REJECTED",
                "reason": "No candidate passed all three gates.",
                "all_candidates": [(c.name, c.gates_passed, c.rate_error, c.recon_error, c.pred_error) for c in candidates]
            }


# ============================================================
# DEMONSTRATION
# ============================================================

def main():
    random.seed(42)

    print("=" * 72)
    print("AEGIS DISCOVERY ENGINE v2 – True Structure Discovery")
    print("=" * 72)
    print()

    # Quadratic data
    print("[1] Quadratic data (y = x^2 + 0.35x + noise)")
    x_vals = [-1.73, -1.41, -1.08, -0.82, -0.53, -0.21,
              0.14, 0.39, 0.67, 0.91, 1.18, 1.47, 1.82]
    y_vals = [(x*x) + 0.35*x + random.gauss(0.0, 0.01) for x in x_vals]
    engine = AEGIS_Discovery()
    result = engine.run(x_vals, y_vals)
    print(f"  Status: {result['status']}")
    if result['status'] == 'PROMOTED':
        print(f"  Best shape: {result['best_shape']}")
        print(f"  Params: {result['params']}")
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
    engine = AEGIS_Discovery()
    result = engine.run(x_linear, y_linear)
    print(f"  Status: {result['status']}")
    if result['status'] == 'PROMOTED':
        print(f"  Best shape: {result['best_shape']}")
        print(f"  Params: {result['params']}")
    print()

    # Exponential data
    print("[3] Exponential data (y = 2*exp(0.5*x) + 1)")
    x_exp = [i/2.0 for i in range(-4, 6)]
    y_exp = [2*math.exp(0.5*x) + 1 + random.gauss(0.0, 0.02) for x in x_exp]
    engine = AEGIS_Discovery()
    result = engine.run(x_exp, y_exp)
    print(f"  Status: {result['status']}")
    if result['status'] == 'PROMOTED':
        print(f"  Best shape: {result['best_shape']}")
        print(f"  Params: {result['params']}")
    print()

    # Pure noise
    print("[4] Pure noise")
    random.seed(99)
    x_noise = [i/10.0 for i in range(30)]
    y_noise = [random.gauss(0.0, 1.0) for _ in range(30)]
    engine = AEGIS_Discovery()
    result = engine.run(x_noise, y_noise)
    print(f"  Status: {result['status']}")
    if result['status'] == 'REJECTED':
        print(f"  Reason: {result.get('reason', 'N/A')}")
    print("=" * 72)

if __name__ == "__main__":
    main()
