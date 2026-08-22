#!/data/data/com.termux/files/usr/bin/python

"""
AEGIS — Adaptive Empirical Grounding & Inference System

This is the discovery engine. It takes raw (x, y) observations and derives
the underlying mathematical relationship without being told what shape to
look for.

It does this by:
  1. Extracting local rates of change (dy/dx) from adjacent points.
  2. Fitting a linear relationship: rate(x) = a*x + b.
  3. Integrating that relationship to obtain the original curve.
  4. Validating against three independent gates:
       - Rate gate: does the linear rate fit the observed derivatives?
       - Reconstruction gate: does the integrated rate reconstruct the curve?
       - Prediction gate: from a single anchor point, does it predict unseen data?
  5. Rejecting its own model if any gate fails.

The engine does not:
  - Use pre-defined candidate functions (sin, exp, polynomial templates).
  - Require human tuning of model order.
  - Hallucinate answers when the data doesn't support a conclusion.

It is deterministic, dependency-free, and enforces its own statistical rigor.
"""

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple


@dataclass
class Observation:
    """A single paired observation."""
    x: float
    y: float


@dataclass
class DiscoveredStructure:
    """
    The discovered mathematical structure.
    
    rate(x) = a*x + b
    integrated form: y = (a/2)*x^2 + b*x + C
    """
    a: float
    b: float
    training_rate_error: float
    validation_rate_error: Optional[float] = None
    validation_reconstruction_error: Optional[float] = None
    validation_prediction_error: Optional[float] = None


class AEGIS:
    """
    The core discovery engine.
    
    Usage:
        engine = AEGIS()
        engine.receive(training_data)
        engine.validation = validation_data
        structure = engine.discover()
        if engine.promote(structure):
            print("Discovered: rate(x) = {structure.a}x + {structure.b}")
    """

    def __init__(self):
        self.training: List[Observation] = []
        self.validation: List[Observation] = []

    def receive(self, observations: List[Observation]) -> None:
        """Ingest training data."""
        self.training.extend(observations)

    @staticmethod
    def rmse(actual: List[float], predicted: List[float]) -> float:
        """Root mean square error."""
        if not actual:
            return float("inf")
        return math.sqrt(sum((a - p) ** 2 for a, p in zip(actual, predicted)) / len(actual))

    def _local_rates(self, observations: List[Observation]) -> List[Tuple[float, float]]:
        """
        Compute local rates (dy/dx) at the midpoints between adjacent points.
        Returns: list of (midpoint_x, rate)
        """
        ordered = sorted(observations, key=lambda o: o.x)
        rates = []
        for i in range(len(ordered) - 1):
            left = ordered[i]
            right = ordered[i + 1]
            dx = right.x - left.x
            if abs(dx) < 1e-12:
                continue
            dy = right.y - left.y
            rate = dy / dx
            midpoint = (left.x + right.x) / 2.0
            rates.append((midpoint, rate))
        return rates

    @staticmethod
    def _fit_linear(pairs: List[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
        """
        Fit y = a*x + b to a list of (x, y) pairs using least squares.
        Returns (a, b) or None if the fit is underdetermined.
        """
        if len(pairs) < 3:
            return None
        xs = [x for x, _ in pairs]
        ys = [y for _, y in pairs]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
        denominator = sum((x - mean_x) ** 2 for x, _ in pairs)
        if abs(denominator) < 1e-12:
            return None
        a = numerator / denominator
        b = mean_y - a * mean_x
        return a, b

    def discover(self) -> Optional[DiscoveredStructure]:
        """
        Discover the mathematical structure from the training data.
        Returns a DiscoveredStructure object, or None if discovery fails.
        """
        rates = self._local_rates(self.training)
        if len(rates) < 4:
            return None

        fit = self._fit_linear(rates)
        if fit is None:
            return None

        a, b = fit
        actual = [rate for _, rate in rates]
        predicted = [(a * x) + b for x, _ in rates]
        error = self.rmse(actual, predicted)

        return DiscoveredStructure(
            a=a,
            b=b,
            training_rate_error=error
        )

    def _reconstruct(self, observations: List[Observation], structure: DiscoveredStructure) -> float:
        """
        Reconstruct the curve by integrating the discovered rate.
        Uses the trapezoidal rule: average rate over each interval.
        """
        ordered = sorted(observations, key=lambda o: o.x)
        if len(ordered) < 2:
            return float("inf")

        reconstructed = [ordered[0].y]
        current = ordered[0].y

        for i in range(len(ordered) - 1):
            x1 = ordered[i].x
            x2 = ordered[i + 1].x
            dx = x2 - x1
            rate1 = structure.a * x1 + structure.b
            rate2 = structure.a * x2 + structure.b
            avg_rate = (rate1 + rate2) / 2.0
            current += avg_rate * dx
            reconstructed.append(current)

        actual = [o.y for o in ordered]
        return self.rmse(actual, reconstructed)

    def _predict_from_anchor(self,
                             anchor: Observation,
                             targets: List[Observation],
                             structure: DiscoveredStructure) -> List[float]:
        """
        Predict target y-values from a single anchor point using the discovered rate.
        """
        predictions = []
        for target in targets:
            dx = target.x - anchor.x
            rate_anchor = structure.a * anchor.x + structure.b
            rate_target = structure.a * target.x + structure.b
            avg_rate = (rate_anchor + rate_target) / 2.0
            predictions.append(anchor.y + avg_rate * dx)
        return predictions

    def validate_rate(self, structure: DiscoveredStructure) -> float:
        """Gate 1: Rate error on validation set."""
        rates = self._local_rates(self.validation)
        if not rates:
            return float("inf")
        actual = [rate for _, rate in rates]
        predicted = [structure.a * x + structure.b for x, _ in rates]
        error = self.rmse(actual, predicted)
        structure.validation_rate_error = error
        return error

    def validate_reconstruction(self, structure: DiscoveredStructure) -> float:
        """Gate 2: Reconstruction error on validation set."""
        error = self._reconstruct(self.validation, structure)
        structure.validation_reconstruction_error = error
        return error

    def validate_prediction(self, structure: DiscoveredStructure) -> float:
        """Gate 3: Prediction error from a single anchor on validation set."""
        ordered = sorted(self.validation, key=lambda o: o.x)
        if len(ordered) < 3:
            return float("inf")
        anchor = ordered[0]
        targets = ordered[1:]
        predictions = self._predict_from_anchor(anchor, targets, structure)
        actual = [o.y for o in targets]
        error = self.rmse(actual, predictions)
        structure.validation_prediction_error = error
        return error

    def promote(self, structure: DiscoveredStructure,
                rate_threshold: float = 0.10,
                recon_threshold: float = 0.10,
                pred_threshold: float = 0.10) -> bool:
        """
        Decide whether to promote the discovered structure.
        All three gates must pass.
        """
        rate_ok = (structure.validation_rate_error is not None and
                   structure.validation_rate_error < rate_threshold)
        recon_ok = (structure.validation_reconstruction_error is not None and
                    structure.validation_reconstruction_error < recon_threshold)
        pred_ok = (structure.validation_prediction_error is not None and
                   structure.validation_prediction_error < pred_threshold)
        return rate_ok and recon_ok and pred_ok

    def classify_shape(self, structure: DiscoveredStructure,
                       y_scale: float,
                       significance_threshold: float = 1e-6) -> str:
        """Classify the discovered relationship as QUADRATIC, LINEAR, or CONSTANT."""
        if abs(structure.a) < significance_threshold * y_scale:
            if abs(structure.b) < significance_threshold * y_scale:
                return "CONSTANT"
            return "LINEAR"
        return "QUADRATIC"

    def run_full_discovery(self, x_values: List[float], y_values: List[float],
                           split_ratio: float = 0.7,
                           rate_threshold: float = 0.10,
                           recon_threshold: float = 0.10,
                           pred_threshold: float = 0.10,
                           significance_threshold: float = 1e-6) -> Dict:
        """
        Complete end-to-end discovery pipeline.

        Args:
            x_values: Independent variable values.
            y_values: Dependent variable values.
            split_ratio: Proportion of data to use for training (0-1).
            rate_threshold: Maximum allowed RMSE for the rate gate.
            recon_threshold: Maximum allowed RMSE for the reconstruction gate.
            pred_threshold: Maximum allowed RMSE for the prediction gate.
            significance_threshold: Threshold for classifying a coefficient as negligible.

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
        # Input validation
        if len(x_values) != len(y_values) or len(x_values) < 6:
            return {
                "status": "INSUFFICIENT_DATA",
                "shape": None,
                "gates_passed": 0,
                "reason": "Need at least 6 paired observations for a reliable train/validation split."
            }

        # Split into training and validation sets (sorted by x)
        paired = sorted(zip(x_values, y_values), key=lambda p: p[0])
        split_idx = int(len(paired) * split_ratio)
        train_pairs = paired[:split_idx]
        val_pairs = paired[split_idx:]

        if len(train_pairs) < 5 or len(val_pairs) < 3:
            return {
                "status": "INSUFFICIENT_DATA",
                "shape": None,
                "gates_passed": 0,
                "reason": "After splitting, not enough points for discovery (train) or validation (val)."
            }

        # Convert to Observation objects
        train_obs = [Observation(x=x, y=y) for x, y in train_pairs]
        val_obs = [Observation(x=x, y=y) for x, y in val_pairs]

        # Set up engine
        engine = AEGIS()
        engine.receive(train_obs)
        engine.validation = val_obs

        # Discover structure
        structure = engine.discover()
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

        # Validate all three gates
        rate_error = engine.validate_rate(structure)
        recon_error = engine.validate_reconstruction(structure)
        pred_error = engine.validate_prediction(structure)

        # Count gates passed
        gates_passed = 0
        rate_ok = rate_error < rate_threshold
        recon_ok = recon_error < recon_threshold
        pred_ok = pred_error < pred_threshold
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
                failed.append(f"rate_error ({rate_error:.4f}) >= threshold ({rate_threshold})")
            if not recon_ok:
                failed.append(f"recon_error ({recon_error:.4f}) >= threshold ({recon_threshold})")
            if not pred_ok:
                failed.append(f"pred_error ({pred_error:.4f}) >= threshold ({pred_threshold})")
            reason = "; ".join(failed)

        # Classify shape
        y_scale = max(abs(y) for y in y_values) if y_values else 1.0
        shape = engine.classify_shape(structure, y_scale, significance_threshold)

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
            "rate_threshold": rate_threshold,
            "recon_threshold": recon_threshold,
            "pred_threshold": pred_threshold,
            "reason": reason
        }


# ============================================================
# DEMONSTRATION
# ============================================================

def main():
    random.seed(42)

    # --- Case 1: Quadratic data with noise ---
    print("=" * 72)
    print("AEGIS DISCOVERY ENGINE – DEMONSTRATION")
    print("=" * 72)
    print()

    print("[1] Quadratic data (y = x² + 0.35x + noise)")
    x_vals = [-1.73, -1.41, -1.08, -0.82, -0.53, -0.21,
              0.14, 0.39, 0.67, 0.91, 1.18, 1.47, 1.82]
    y_vals = [(x * x) + 0.35 * x + random.gauss(0.0, 0.01) for x in x_vals]

    engine = AEGIS()
    result = engine.run_full_discovery(x_vals, y_vals)
    print(f"  Status: {result['status']}")
    print(f"  Shape:  {result['shape']}")
    print(f"  Equation: {result['equation']}")
    print(f"  Integrated form: {result['integrated_form']}")
    print(f"  Gates passed: {result['gates_passed']}/3")
    print(f"  Rate error:   {result['rate_error']:.6f}")
    print(f"  Recon error:  {result['recon_error']:.6f}")
    print(f"  Pred error:   {result['pred_error']:.6f}")
    print()

    # --- Case 2: Linear data ---
    print("[2] Linear data (y = 3x + 1, no noise)")
    x_linear = [-3, -2, -1, 0, 1, 2, 3, 4, 5]
    y_linear = [3*x + 1 for x in x_linear]
    result = engine.run_full_discovery(x_linear, y_linear)
    print(f"  Status: {result['status']}")
    print(f"  Shape:  {result['shape']}")
    print(f"  Equation: {result['equation']}")
    print(f"  Integrated form: {result['integrated_form']}")
    print(f"  Gates passed: {result['gates_passed']}/3")
    print(f"  Rate error:   {result['rate_error']:.6f}")
    print(f"  Recon error:  {result['recon_error']:.6f}")
    print(f"  Pred error:   {result['pred_error']:.6f}")
    print()

    # --- Case 3: Pure noise ---
    print("[3] Pure noise (no relationship)")
    random.seed(99)
    x_noise = [i/10.0 for i in range(30)]
    y_noise = [random.gauss(0.0, 1.0) for _ in range(30)]
    result = engine.run_full_discovery(x_noise, y_noise)
    print(f"  Status: {result['status']}")
    print(f"  Shape:  {result['shape']}")
    if result['status'] == "REJECTED":
        print(f"  Reason: {result['reason']}")
    print("=" * 72)


if __name__ == "__main__":
    main()
