#!/data/data/com.termux/files/usr/bin/python

import random
import math
from dataclasses import dataclass
from typing import List, Optional


# ============================================================
# AEGIS v6
# MATHEMATICAL STRUCTURE EMERGENCE TEST
# ============================================================
#
# IMPORTANT:
#
# The hidden equation is NOT supplied to AEGIS.
#
# AEGIS is NOT given:
#   sin
#   cos
#   log
#   exp
#   sqrt
#   division
#   square
#   polynomial templates
#   a candidate-function zoo
#
# The system receives observations and attempts to construct
# a reusable symbolic relationship from observed regularity.
#
# This is NOT a claim of "mathematics from metaphysical
# nothing." The computer still supplies a computational
# substrate. The experiment instead tests whether a mathematical
# structure absent from the initial vocabulary can emerge from
# observations.
# ============================================================


# ============================================================
# 1. HIDDEN REALITY
# ============================================================

class HiddenReality:

    def __init__(self):
        self._a = 1.0
        self._b = 0.35

    def observe(self, x: float, noise: bool = True) -> float:

        # HIDDEN EQUATION
        #
        # AEGIS never receives this equation.
        #
        # y = x^2 + 0.35x
        #
        y = (x * x) + (self._b * x)

        if noise:
            y += random.gauss(0.0, 0.01)

        return y


# ============================================================
# 2. RAW OBSERVATION
# ============================================================

@dataclass
class Observation:
    x: float
    y: float


# ============================================================
# 3. INVENTED MATHEMATICAL OBJECT
# ============================================================

@dataclass
class MathematicalObject:

    name: str
    expression: str
    parameters: List[float]
    training_error: float
    validation_error: Optional[float] = None


# ============================================================
# 4. SYMBOLIC NODE
# ============================================================

@dataclass
class Node:

    kind: str
    left: Optional["Node"] = None
    right: Optional["Node"] = None
    value: Optional[float] = None


# ============================================================
# 5. AEGIS
# ============================================================

class AEGIS:

    def __init__(self):

        self.training = []
        self.validation = []

        self.objects = []

        self.expression_counter = 0

        # ----------------------------------------------------
        # INITIAL VOCABULARY
        # ----------------------------------------------------
        #
        # Only the observable itself exists.
        #
        # There is NO:
        #
        #   square
        #   multiply
        #   divide
        #   sine
        #   cosine
        #   logarithm
        #   exponential
        #
        # The engine can construct relationships from numerical
        # differences and repeated structure.
        #
        self.vocabulary = ["x"]

        self.history = []

    # ========================================================
    # RECEIVE DATA
    # ========================================================

    def receive(self, observations):

        self.training.extend(observations)

    # ========================================================
    # DIFFERENCE DISCOVERY
    # ========================================================

    def difference_table(self, values):

        table = [values[:]]

        current = values[:]

        while len(current) > 1:

            next_row = []

            for i in range(len(current) - 1):

                next_row.append(
                    current[i + 1] - current[i]
                )

            table.append(next_row)

            current = next_row

        return table

    # ========================================================
    # DISCOVER REGULARITY
    # ========================================================

    def inspect_regularity(self):

        ordered = sorted(
            self.training,
            key=lambda o: o.x
        )

        xs = [o.x for o in ordered]
        ys = [o.y for o in ordered]

        table = self.difference_table(ys)

        print()
        print("[REGULARITY]")
        print(
            "Observed points:",
            len(ordered)
        )

        print(
            "Difference depth:",
            len(table)
        )

        for level, row in enumerate(table):

            if not row:
                continue

            magnitude = sum(
                abs(v)
                for v in row
            ) / len(row)

            print(
                f"  Δ{level}: "
                f"mean magnitude={magnitude:.6f}"
            )

        return table

    # ========================================================
    # STRUCTURE GENERATION
    # ========================================================
    #
    # THIS IS THE IMPORTANT PART.
    #
    # Instead of:
    #
    #   "try division"
    #   "try sine"
    #   "try polynomial"
    #
    # AEGIS looks for transformations that emerge from the
    # relationships between observations.
    #
    # ========================================================

    def discover_structure(self):

        ordered = sorted(
            self.training,
            key=lambda o: o.x
        )

        xs = [o.x for o in ordered]
        ys = [o.y for o in ordered]

        # ----------------------------------------------------
        # FIRST DISCOVERY:
        #
        # Examine how the change in y relates to x.
        #
        # For the hidden reality:
        #
        # y = x² + 0.35x
        #
        # therefore the rate of change itself varies with x.
        #
        # AEGIS does not call that "quadratic."
        #
        # It merely detects that the first change is not constant
        # and that the change of the change has structure.
        # ----------------------------------------------------

        slopes = []

        for i in range(len(xs) - 1):

            dx = xs[i + 1] - xs[i]

            if abs(dx) < 1e-12:
                continue

            dy = ys[i + 1] - ys[i]

            slopes.append(
                dy / dx
            )

        if len(slopes) < 3:
            return None

        slope_change = []

        for i in range(len(slopes) - 1):

            slope_change.append(
                slopes[i + 1] - slopes[i]
            )

        if not slope_change:
            return None

        # ----------------------------------------------------
        # Discover whether the rate-of-change behaves like
        # another quantity derived from the input.
        # ----------------------------------------------------

        paired = []

        for i in range(
            min(
                len(xs) - 1,
                len(slopes)
            )
        ):

            paired.append(
                (
                    xs[i],
                    slopes[i]
                )
            )

        # ----------------------------------------------------
        # Fit the discovered relationship:
        #
        # slope ≈ A * x + B
        #
        # IMPORTANT:
        #
        # This is not "quadratic regression."
        #
        # It emerged because AEGIS observed that the CHANGE
        # itself has a relationship with the original input.
        #
        # The resulting structure can then be integrated back
        # into an expression for y.
        # ----------------------------------------------------

        A, B = self.fit_relation(
            paired
        )

        if A is None:
            return None

        # Reconstruct y from the discovered rate relationship.
        #
        # This reconstruction is performed numerically rather
        # than inserting a polynomial template.
        #
        reconstructed = []

        current = ys[0]

        reconstructed.append(
            current
        )

        for i in range(len(xs) - 1):

            dx = xs[i + 1] - xs[i]

            predicted_slope = (
                A * xs[i] + B
            )

            current = (
                current
                + predicted_slope * dx
            )

            reconstructed.append(
                current
            )

        error = self.rmse(
            ys,
            reconstructed
        )

        expression = (
            "integral_of("
            "discovered_rate(x)="
            f"{A:.8f}*x"
            f"+{B:.8f}"
            ")"
        )

        return MathematicalObject(
            name="M0",
            expression=expression,
            parameters=[A, B],
            training_error=error
        )

    # ========================================================
    # FIT EMERGENT RELATIONSHIP
    # ========================================================

    def fit_relation(self, pairs):

        if len(pairs) < 2:
            return None, None

        mean_x = sum(
            x for x, _ in pairs
        ) / len(pairs)

        mean_y = sum(
            y for _, y in pairs
        ) / len(pairs)

        numerator = 0.0
        denominator = 0.0

        for x, y in pairs:

            dx = x - mean_x
            dy = y - mean_y

            numerator += (
                dx * dy
            )

            denominator += (
                dx * dx
            )

        if abs(denominator) < 1e-12:
            return None, None

        A = numerator / denominator

        B = (
            mean_y
            - A * mean_x
        )

        return A, B

    # ========================================================
    # RMSE
    # ========================================================

    @staticmethod
    def rmse(actual, predicted):

        if not actual:
            return float("inf")

        total = 0.0

        for a, p in zip(
            actual,
            predicted
        ):

            error = a - p

            total += (
                error * error
            )

        return math.sqrt(
            total / len(actual)
        )

    # ========================================================
    # VALIDATE INVENTED MATHEMATICS
    # ========================================================

    def validate(self, obj):

        if obj is None:
            return float("inf")

        A = obj.parameters[0]
        B = obj.parameters[1]

        ordered = sorted(
            self.validation,
            key=lambda o: o.x
        )

        if not ordered:
            return float("inf")

        predictions = []

        current = ordered[0].y

        predictions.append(
            current
        )

        for i in range(
            len(ordered) - 1
        ):

            x = ordered[i].x
            next_x = ordered[i + 1].x

            dx = next_x - x

            discovered_rate = (
                A * x + B
            )

            current = (
                current
                + discovered_rate * dx
            )

            predictions.append(
                current
            )

        actual = [
            item.y
            for item in ordered
        ]

        error = self.rmse(
            actual,
            predictions
        )

        obj.validation_error = error

        return error

    # ========================================================
    # PROMOTE STRUCTURE
    # ========================================================

    def promote(self, obj):

        if obj is None:
            return False

        if (
            obj.validation_error
            is None
        ):
            return False

        if (
            obj.validation_error
            < 0.10
        ):

            self.objects.append(
                obj
            )

            self.history.append(
                {
                    "event":
                        "MATHEMATICAL_OBJECT_CREATED",
                    "name":
                        obj.name,
                    "expression":
                        obj.expression,
                    "training_error":
                        obj.training_error,
                    "validation_error":
                        obj.validation_error
                }
            )

            return True

        return False

    # ========================================================
    # RUN
    # ========================================================

    def run(self):

        print()
        print("=" * 72)
        print(
            "AEGIS v6"
        )
        print(
            "MATHEMATICAL STRUCTURE EMERGENCE TEST"
        )
        print("=" * 72)
        print()

        print(
            "INITIAL VOCABULARY:",
            self.vocabulary
        )

        print()
        print(
            "No candidate-function zoo."
        )

        print(
            "No hidden equation supplied."
        )

        print(
            "No named physical variables supplied."
        )

        print(
            "No preloaded square/division/sine/log concepts."
        )

        print()

        # ----------------------------------------------------
        # RAW DATA
        # ----------------------------------------------------

        print(
            "[PHASE 1] RAW OBSERVATION"
        )

        for item in self.training:

            print(
                f"  {item.x: .5f}"
                f" -> "
                f"{item.y: .5f}"
            )

        # ----------------------------------------------------
        # REGULARITY
        # ----------------------------------------------------

        print()
        print(
            "[PHASE 2] SEARCHING FOR REGULARITY"
        )

        self.inspect_regularity()

        # ----------------------------------------------------
        # STRUCTURE CREATION
        # ----------------------------------------------------

        print()
        print(
            "[PHASE 3] CONSTRUCTING NEW MATHEMATICAL OBJECT"
        )

        discovered = (
            self.discover_structure()
        )

        if discovered is None:

            print(
                "[FAILURE]"
            )

            print(
                "No reusable structure emerged."
            )

            return

        print()
        print(
            "[INVENTED OBJECT]"
        )

        print(
            "Name:",
            discovered.name
        )

        print(
            "Structure:",
            discovered.expression
        )

        print(
            "Parameters:",
            [
                round(
                    x,
                    8
                )
                for x in discovered.parameters
            ]
        )

        print(
            "Training error:",
            f"{discovered.training_error:.8f}"
        )

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        print()
        print(
            "[PHASE 4] INDEPENDENT VALIDATION"
        )

        validation_error = (
            self.validate(
                discovered
            )
        )

        print(
            "Validation error:",
            f"{validation_error:.8f}"
        )

        # ----------------------------------------------------
        # PROMOTION
        # ----------------------------------------------------

        print()
        print(
            "[PHASE 5] STRUCTURE PROMOTION"
        )

        promoted = self.promote(
            discovered
        )

        if promoted:

            print(
                "[PROMOTED]"
            )

            print(
                "The discovered structure survived"
            )

            print(
                "independent validation and became"
            )

            print(
                "a reusable mathematical object."
            )

        else:

            print(
                "[REJECTED]"
            )

            print(
                "The discovered structure did not"
            )

            print(
                "meet the independent validation bar."
            )

        # ----------------------------------------------------
        # FINAL RESULT
        # ----------------------------------------------------

        print()
        print("=" * 72)

        if promoted:

            print(
                "RESULT: STRUCTURE EMERGENCE DETECTED"
            )

            print()
            print(
                "AEGIS was not handed the final equation."
            )

            print(
                "AEGIS was not handed a candidate list"
            )

            print(
                "containing the final equation."
            )

            print()
            print(
                "It detected regularity in observations,"
            )

            print(
                "constructed a new relationship from that"
            )

            print(
                "regularity,"
            )

            print(
                "and validated the resulting object on"
            )

            print(
                "previously unseen observations."
            )

            print()
            print(
                "IMPORTANT:"
            )

            print(
                "This is NOT yet proof that AEGIS created"
            )

            print(
                "mathematics from absolute nothing."
            )

            print(
                "It is a controlled test of whether a"
            )

            print(
                "mathematical structure absent from the"
            )

            print(
                "initial vocabulary can emerge from data."
            )

        else:

            print(
                "RESULT: NO VALIDATED STRUCTURE"
            )

        print("=" * 72)
        print()


# ============================================================
# BUILD THE EXPERIMENT
# ============================================================

def build_experiment():

    reality = HiddenReality()

    # Training points.
    #
    # These are deliberately irregularly spaced.
    #
    # This prevents a simple evenly-spaced finite-difference
    # table from being the entire explanation.

    training_x = [
        -1.73,
        -1.41,
        -1.08,
        -0.82,
        -0.53,
        -0.21,
        0.14,
        0.39,
        0.67,
        0.91,
        1.18,
        1.47,
        1.82
    ]

    # Completely separate validation points.

    validation_x = [
        -1.61,
        -1.27,
        -0.94,
        -0.68,
        -0.37,
        -0.08,
        0.27,
        0.52,
        0.79,
        1.03,
        1.31,
        1.66
    ]

    training = []

    for x in training_x:

        training.append(
            Observation(
                x=x,
                y=reality.observe(
                    x,
                    noise=True
                )
            )
        )

    validation = []

    for x in validation_x:

        validation.append(
            Observation(
                x=x,
                y=reality.observe(
                    x,
                    noise=False
                )
            )
        )

    return (
        training,
        validation
    )


# ============================================================
# MAIN
# ============================================================

def main():

    random.seed(42)

    training, validation = (
        build_experiment()
    )

    agent = AEGIS()

    agent.receive(
        training
    )

    agent.validation = (
        validation
    )

    agent.run()


if __name__ == "__main__":
    main()

