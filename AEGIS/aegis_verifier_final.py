#!/data/data/com.termux/files/usr/bin/python

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

@dataclass
class Observation:
    x: float
    y: float

@dataclass
class Structure:
    a: float
    b: float
    training_rate_error: float


class AEGIS_QuadraticVerifier:
    """
    A deterministic, dependency‑free verifier that checks whether
    a given (x, y) dataset is consistent with a quadratic relationship.

    It enforces an internal train/validation split (70/30, sorted by x)
    before performing any discovery or validation. The three gates are
    evaluated strictly on the validation set.

    It distinguishes between QUADRATIC, LINEAR, and CONSTANT shapes
    by checking the magnitude of the x² coefficient against the data scale.
    """

    def __init__(self,
                 split_ratio: float = 0.7,
                 rate_threshold: float = 0.10,
                 recon_threshold: float = 0.10,
                 pred_threshold: float = 0.10,
                 significance_threshold: float = 1e-6):
        self.split_ratio = split_ratio
        self.rate_threshold = rate_threshold
        self.recon_threshold = recon_threshold
        self.pred_threshold = pred_threshold
        self.significance_threshold = significance_threshold

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

    def _fit_linear(self, pairs: List[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
        if len(pairs) < 3:
            return None
        mean_x = sum(x for x, _ in pairs) / len(pairs)
        mean_y = sum(y for _, y in pairs) / len(pairs)
        num = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
        den = sum((x - mean_x) ** 2 for x, _ in pairs)
        if abs(den) < 1e-12:
            return None
        a = num / den
        b = mean_y - a * mean_x
        return a, b

    def _discover(self, observations: List[Observation]) -> Optional[Structure]:
        rates = self._local_rates(observations)
        if len(rates) < 4:
            return None
        fit = self._fit_linear(rates)
        if fit is None:
            return None
        a, b = fit
        actual = [r for _, r in rates]
        predicted = [(a * x) + b for x, _ in rates]
        error = self.rmse(actual, predicted)
        return Structure(a=a, b=b, training_rate_error=error)

    def _reconstruct(self, observations: List[Observation], structure: Structure) -> float:
        ordered = sorted(observations, key=lambda o: o.x)
        if len(ordered) < 2:
            return float("inf")
        reconstructed = [ordered[0].y]
        current = ordered[0].y
        for i in range(len(ordered) - 1):
            x1, x2 = ordered[i].x, ordered[i + 1].x
            dx = x2 - x1
            avg_rate = (structure.a * x1 + structure.b + structure.a * x2 + structure.b) / 2.0
            current += avg_rate * dx
            reconstructed.append(current)
        actual = [o.y for o in ordered]
        return self.rmse(actual, reconstructed)

    def _predict_from_anchor(self, anchor: Observation,
                             targets: List[Observation],
                             structure: Structure) -> List[float]:
        preds = []
        for t in targets:
            dx = t.x - anchor.x
            avg_rate = (structure.a * anchor.x + structure.b + structure.a * t.x + structure.b) / 2.0
            preds.append(anchor.y + avg_rate * dx)
        return preds

    def _classify_shape(self, a: float, b: float, y_scale: float) -> str:
        if abs(a) < self.significance_threshold * y_scale:
            # If slope is also negligible, call it constant; otherwise linear
            if abs(b) < self.significance_threshold * y_scale:
                return "CONSTANT"
            return "LINEAR"
        return "QUADRATIC"

    def validate(self, x_values: List[float], y_values: List[float]) -> Dict:
        """
        Validates whether the given data is consistent with a quadratic form.
        Returns:
            {
                "status": "PROMOTED" | "REJECTED" | "INSUFFICIENT_DATA",
                "shape": "QUADRATIC" | "LINEAR" | "CONSTANT" | None,
                "gates_passed": int (0-3),
                "equation": "rate(x) = a*x + b",
                "integrated_form": "y ~= (a/2)*x^2 + b*x + C",
                "rate_error": float,
                "recon_error": float,
                "pred_error": float,
                "rate_threshold": float,
                "recon_threshold": float,
                "pred_threshold": float,
                "reason": str (if REJECTED)
            }
        """
        if len(x_values) != len(y_values) or len(x_values) < 6:
            return {
                "status": "INSUFFICIENT_DATA",
                "shape": None,
                "gates_passed": 0,
                "reason": "Need at least 6 paired observations for a reliable train/validation split."
            }

        # Sort by x and split (70/30) – deterministic, no leakage
        paired = sorted(zip(x_values, y_values), key=lambda p: p[0])
        split_idx = int(len(paired) * self.split_ratio)
        train_pairs = paired[:split_idx]
        val_pairs = paired[split_idx:]

        if len(train_pairs) < 5 or len(val_pairs) < 3:
            return {
                "status": "INSUFFICIENT_DATA",
                "shape": None,
                "gates_passed": 0,
                "reason": "After splitting, not enough points for discovery (train) or validation (val)."
            }

        train_obs = [Observation(x=x, y=y) for x, y in train_pairs]
        val_obs = [Observation(x=x, y=y) for x, y in val_pairs]

        # 1. Discover on training set only
        structure = self._discover(train_obs)
        if structure is None:
            return {
                "status": "REJECTED",
                "shape": None,
                "gates_passed": 0,
                "reason": "Could not extract a stable linear rate relationship from the training set.",
                "equation": None,
                "integrated_form": None,
                "rate_error": None,
                "recon_error": None,
                "pred_error": None,
            }

        # 2. Evaluate all gates on validation set only
        val_rates = self._local_rates(val_obs)
        if not val_rates:
            return {
                "status": "REJECTED",
                "shape": None,
                "gates_passed": 0,
                "reason": "Validation set has fewer than 2 points for rate extraction.",
                "equation": None,
                "integrated_form": None,
                "rate_error": None,
                "recon_error": None,
                "pred_error": None,
            }

        # Gate 1: Rate error on validation set
        actual_rates = [r for _, r in val_rates]
        pred_rates = [(structure.a * x + structure.b) for x, _ in val_rates]
        rate_error = self.rmse(actual_rates, pred_rates)

        # Gate 2: Reconstruction error on validation set
        recon_error = self._reconstruct(val_obs, structure)

        # Gate 3: Prediction from a single anchor on validation set
        ordered_val = sorted(val_obs, key=lambda o: o.x)
        if len(ordered_val) < 3:
            pred_error = float("inf")
        else:
            anchor = ordered_val[0]
            targets = ordered_val[1:]
            preds = self._predict_from_anchor(anchor, targets, structure)
            actual = [o.y for o in targets]
            pred_error = self.rmse(actual, preds)

        # Count gates
        gates_passed = 0
        rate_ok = rate_error < self.rate_threshold
        recon_ok = recon_error < self.recon_threshold
        pred_ok = pred_error < self.pred_threshold
        if rate_ok:
            gates_passed += 1
        if recon_ok:
            gates_passed += 1
        if pred_ok:
            gates_passed += 1

        status = "PROMOTED" if gates_passed == 3 else "REJECTED"
        reason = None
        if status == "REJECTED":
            failed = []
            if not rate_ok:
                failed.append(f"rate_error ({rate_error:.4f}) >= threshold ({self.rate_threshold})")
            if not recon_ok:
                failed.append(f"recon_error ({recon_error:.4f}) >= threshold ({self.recon_threshold})")
            if not pred_ok:
                failed.append(f"pred_error ({pred_error:.4f}) >= threshold ({self.pred_threshold})")
            reason = "; ".join(failed)

        # 3. Classify shape using coefficient significance
        y_scale = max(abs(y) for y in y_values) if y_values else 1.0
        shape = self._classify_shape(structure.a, structure.b, y_scale)

        integrated = f"y ~= {structure.a/2:.6f}*x^2 + {structure.b:.6f}*x + C"

        return {
            "status": status,
            "shape": shape,
            "gates_passed": gates_passed,
            "equation": f"rate(x) = {structure.a:.8f}*x + {structure.b:.8f}",
            "integrated_form": integrated,
            "rate_error": rate_error,
            "recon_error": recon_error,
            "pred_error": pred_error,
            "rate_threshold": self.rate_threshold,
            "recon_threshold": self.recon_threshold,
            "pred_threshold": self.pred_threshold,
            "reason": reason
        }


# --- Example usage (smoke test) ---
if __name__ == "__main__":
    random.seed(42)
    bias = 0.35
    x_vals = [-1.73, -1.41, -1.08, -0.82, -0.53, -0.21,
              0.14, 0.39, 0.67, 0.91, 1.18, 1.47, 1.82]
    y_vals = [(x * x) + bias * x + random.gauss(0.0, 0.01) for x in x_vals]

    verifier = AEGIS_QuadraticVerifier()
    result = verifier.validate(x_vals, y_vals)

    import json
    print("Quadratic test:")
    print(json.dumps(result, indent=2))

    print("\n" + "-"*50 + "\n")

    # Test linear data
    x_linear = [-3, -2, -1, 0, 1, 2, 3, 4, 5]
    y_linear = [3*x + 1 for x in x_linear]
    result_linear = verifier.validate(x_linear, y_linear)
    print("Linear test:")
    print(json.dumps(result_linear, indent=2))

    # Test constant data
    x_const = [-3, -2, -1, 0, 1, 2, 3, 4, 5]
    y_const = [5.0] * len(x_const)
    result_const = verifier.validate(x_const, y_const)
    print("\n" + "-"*50 + "\n")
    print("Constant test:")
    print(json.dumps(result_const, indent=2))
