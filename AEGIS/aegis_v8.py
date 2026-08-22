#!/data/data/com.termux/files/usr/bin/python

import random
import math
from dataclasses import dataclass
from typing import List, Optional

# ============================================================
# AEGIS V8 – CLOSED MATHEMATICAL STRUCTURE DISCOVERY
# ============================================================
#
# This is the version that WORKS.
# No privileged access. No candidate zoo.
# Three independent validation gates:
#   1. Rate structure
#   2. Reconstruction
#   3. Prediction
#
# All three must pass (RMSE < 0.1) for promotion.
# ============================================================

class HiddenReality:
    def __init__(self):
        self.bias = 0.35

    def observe(self, x: float, noise: bool = True) -> float:
        # Hidden law: y = x^2 + 0.35x
        y = (x * x) + (self.bias * x)
        if noise:
            y += random.gauss(0.0, 0.01)
        return y


@dataclass
class Observation:
    x: float
    y: float


@dataclass
class Structure:
    name: str
    a: float
    b: float
    training_rate_error: float
    validation_rate_error: Optional[float] = None
    validation_reconstruction_error: Optional[float] = None
    validation_prediction_error: Optional[float] = None


class AEGIS:
    def __init__(self):
        self.training: List[Observation] = []
        self.validation: List[Observation] = []
        self.structures: List[Structure] = []
        self.vocabulary = ["x", "observed_change"]

    def receive(self, observations: List[Observation]):
        self.training.extend(observations)

    @staticmethod
    def rmse(actual, predicted):
        if not actual:
            return float("inf")
        total = sum((a - p) ** 2 for a, p in zip(actual, predicted))
        return math.sqrt(total / len(actual))

    def local_rates(self, observations):
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
    def fit_linear_relation(pairs):
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

    def discover(self):
        rates = self.local_rates(self.training)
        if len(rates) < 4:
            return None

        relation = self.fit_linear_relation(rates)
        if relation is None:
            return None

        a, b = relation

        actual = []
        predicted = []
        for x, rate in rates:
            actual.append(rate)
            predicted.append((a * x) + b)

        error = self.rmse(actual, predicted)
        return Structure(
            name="MATH_1",
            a=a,
            b=b,
            training_rate_error=error
        )

    def reconstruct(self, observations, structure):
        ordered = sorted(observations, key=lambda o: o.x)
        if len(ordered) < 2:
            return float("inf")

        predicted = [ordered[0].y]
        current = ordered[0].y

        for i in range(len(ordered) - 1):
            x1 = ordered[i].x
            x2 = ordered[i + 1].x
            dx = x2 - x1
            rate1 = structure.a * x1 + structure.b
            rate2 = structure.a * x2 + structure.b
            average_rate = (rate1 + rate2) / 2.0
            current += average_rate * dx
            predicted.append(current)

        actual = [o.y for o in ordered]
        return self.rmse(actual, predicted)

    def predict_from_anchor(self, anchor, targets, structure):
        predictions = []
        for target_x in targets:
            dx = target_x - anchor.x
            rate_anchor = structure.a * anchor.x + structure.b
            rate_target = structure.a * target_x + structure.b
            average_rate = (rate_anchor + rate_target) / 2.0
            prediction = anchor.y + average_rate * dx
            predictions.append(prediction)
        return predictions

    def validate_rate(self, structure):
        rates = self.local_rates(self.validation)
        if not rates:
            return float("inf")
        actual = [rate for _, rate in rates]
        predicted = [structure.a * x + structure.b for x, _ in rates]
        error = self.rmse(actual, predicted)
        structure.validation_rate_error = error
        return error

    def validate_reconstruction(self, structure):
        error = self.reconstruct(self.validation, structure)
        structure.validation_reconstruction_error = error
        return error

    def validate_prediction(self, structure):
        ordered = sorted(self.validation, key=lambda o: o.x)
        if len(ordered) < 3:
            return float("inf")
        anchor = ordered[0]
        targets = ordered[1:]
        predictions = self.predict_from_anchor(
            anchor,
            [o.x for o in targets],
            structure
        )
        actual = [o.y for o in targets]
        error = self.rmse(actual, predictions)
        structure.validation_prediction_error = error
        return error

    def promote(self, structure):
        rate_ok = (
            structure.validation_rate_error is not None
            and structure.validation_rate_error < 0.10
        )
        recon_ok = (
            structure.validation_reconstruction_error is not None
            and structure.validation_reconstruction_error < 0.10
        )
        pred_ok = (
            structure.validation_prediction_error is not None
            and structure.validation_prediction_error < 0.10
        )
        return rate_ok and recon_ok and pred_ok

    def run(self):
        print("=" * 72)
        print("AEGIS V8 – CLOSED MATHEMATICAL DISCOVERY")
        print("=" * 72)
        print()
        print("[INITIAL VOCABULARY]")
        print(self.vocabulary)
        print()
        print("[TARGET CONCEPTS NOT SUPPLIED]")
        print("square, quadratic, polynomial")
        print("derivative, integral, target equation")
        print()

        print("[PHASE 1] RAW OBSERVATIONS")
        for item in self.training:
            print(f"  x={item.x: .5f}  y={item.y: .5f}")
        print()

        rates = self.local_rates(self.training)
        print(f"[PHASE 2] EXTRACTED {len(rates)} LOCAL CHANGES")
        print()

        structure = self.discover()
        if structure is None:
            print("[FAILURE] No structure discovered.")
            return

        print("[PHASE 3] STRUCTURE DISCOVERED")
        print(f"  Name: {structure.name}")
        print(f"  rate(x) = {structure.a:.12f} * x + {structure.b:.12f}")
        print(f"  Training rate RMSE: {structure.training_rate_error:.10f}")
        print()

        rate_error = self.validate_rate(structure)
        print(f"[PHASE 4] RATE VALIDATION: {rate_error:.10f}")
        print()

        recon_error = self.validate_reconstruction(structure)
        print(f"[PHASE 5] RECONSTRUCTION: {recon_error:.10f}")
        print()

        pred_error = self.validate_prediction(structure)
        print(f"[PHASE 6] PREDICTION: {pred_error:.10f}")
        print()

        print("[PHASE 7] THREE-GATE PROMOTION")
        rate_ok = rate_error < 0.10
        recon_ok = recon_error < 0.10
        pred_ok = pred_error < 0.10
        print(f"  Rate structure: {'PASS' if rate_ok else 'FAIL'}")
        print(f"  Reconstruction: {'PASS' if recon_ok else 'FAIL'}")
        print(f"  Prediction:     {'PASS' if pred_ok else 'FAIL'}")
        print()

        if self.promote(structure):
            self.structures.append(structure)
            print("[PROMOTED] The discovered mathematical structure")
            print("           passed all independent gates.")
            print()
            print("DISCOVERY CHAIN:")
            print("  RAW OBSERVATIONS")
            print("       ↓")
            print("  OBSERVED CHANGE")
            print("       ↓")
            print("  RELATIONSHIP")
            print("       ↓")
            print("  MATHEMATICAL STRUCTURE")
            print("       ↓")
            print("  RECONSTRUCTION")
            print("       ↓")
            print("  INDEPENDENT PREDICTION")
            print("       ↓")
            print("  PROMOTION")
        else:
            print("[REJECTED] The structure did not pass all gates.")

        print("=" * 72)


def build_experiment():
    reality = HiddenReality()
    training_x = [
        -1.73, -1.41, -1.08, -0.82, -0.53, -0.21,
        0.14, 0.39, 0.67, 0.91, 1.18, 1.47, 1.82
    ]
    validation_x = [
        -1.61, -1.27, -0.94, -0.68, -0.37, -0.08,
        0.27, 0.52, 0.79, 1.03, 1.31, 1.66
    ]
    training = [
        Observation(x=x, y=reality.observe(x, noise=True))
        for x in training_x
    ]
    validation = [
        Observation(x=x, y=reality.observe(x, noise=False))
        for x in validation_x
    ]
    return training, validation


def main():
    random.seed(42)
    training, validation = build_experiment()
    agent = AEGIS()
    agent.receive(training)
    agent.validation = validation
    agent.run()


if __name__ == "__main__":
    main()
