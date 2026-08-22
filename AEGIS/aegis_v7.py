#!/data/data/com.termux/files/usr/bin/python

import random
import math
from dataclasses import dataclass
from typing import List, Optional, Callable, Tuple


# ============================================================
# AEGIS v7
# MATHEMATICAL OPERATOR EMERGENCE
# ============================================================
#
# DEVELOPMENTAL STEP:
#
# V6:
#   observations
#       ->
#   discovered relationship
#       ->
#   mathematical object
#
# V7:
#   observations
#       ->
#   discovered relationship
#       ->
#   discover transformation
#       ->
#   construct operator
#       ->
#   validate operator independently
#
# IMPORTANT:
#
# The hidden equation is NOT supplied to AEGIS.
#
# AEGIS is not given:
#
#   square
#   polynomial
#   quadratic
#   derivative
#   integration
#   "x^2"
#
# The system begins with only:
#
#   numerical observations
#
# The computational substrate necessarily contains
# primitive arithmetic because a computer must have
# some mechanism with which to manipulate numbers.
#
# The experiment therefore tests whether a NEW
# mathematical transformation can be constructed
# from observed regularity rather than being supplied
# as the target solution.
# ============================================================


# ============================================================
# 1. HIDDEN REALITY
# ============================================================

class HiddenReality:

    def __init__(self):
        self._bias = 0.35

    def observe(self, x: float, noise: bool = True) -> float:

        # Hidden law.
        #
        # AEGIS never receives this equation.

        y = (x * x) + (self._bias * x)

        if noise:
            y += random.gauss(0.0, 0.01)

        return y


# ============================================================
# 2. OBSERVATION
# ============================================================

@dataclass
class Observation:
    x: float
    y: float


# ============================================================
# 3. DISCOVERED OPERATOR
# ============================================================

@dataclass
class DiscoveredOperator:

    name: str
    expression: str

    # Transformation implemented by the discovered operator.
    function: Callable[[float], float]

    training_error: float
    validation_error: Optional[float] = None

    generation: int = 0


# ============================================================
# 4. AEGIS V7
# ============================================================

class AEGIS:

    def __init__(self):

        self.training: List[Observation] = []
        self.validation: List[Observation] = []

        self.operators: List[DiscoveredOperator] = []

        self.generation = 0

        self.history = []

        # ----------------------------------------------------
        # ONLY RAW OBSERVABLE IS EXPOSED
        # ----------------------------------------------------

        self.vocabulary = [
            "x",
            "observed_change"
        ]

    # ========================================================
    # RECEIVE OBSERVATIONS
    # ========================================================

    def receive(
        self,
        observations: List[Observation]
    ):

        self.training.extend(
            observations
        )

    # ========================================================
    # BASIC STATISTICS
    # ========================================================

    @staticmethod
    def mean(values):

        if not values:
            return 0.0

        return (
            sum(values)
            / len(values)
        )

    @staticmethod
    def rmse(
        actual,
        predicted
    ):

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
    # DISCOVER LOCAL RATE
    # ========================================================
    #
    # AEGIS does not assume that the output itself is
    # the important object.
    #
    # It examines how the output changes as the input
    # changes.
    #
    # ========================================================

    def local_rates(
        self,
        observations
    ):

        ordered = sorted(
            observations,
            key=lambda item: item.x
        )

        rates = []

        for i in range(
            len(ordered) - 1
        ):

            left = ordered[i]
            right = ordered[i + 1]

            dx = (
                right.x
                - left.x
            )

            if abs(dx) < 1e-12:
                continue

            dy = (
                right.y
                - left.y
            )

            rate = (
                dy / dx
            )

            midpoint = (
                left.x
                + right.x
            ) / 2.0

            rates.append(
                (
                    midpoint,
                    rate
                )
            )

        return rates

    # ========================================================
    # DISCOVER SECOND-ORDER STRUCTURE
    # ========================================================

    def rate_changes(
        self,
        rates
    ):

        changes = []

        for i in range(
            len(rates) - 1
        ):

            x1, r1 = rates[i]
            x2, r2 = rates[i + 1]

            dx = x2 - x1

            if abs(dx) < 1e-12:
                continue

            dr = r2 - r1

            changes.append(
                (
                    (x1 + x2) / 2.0,
                    dr / dx
                )
            )

        return changes

    # ========================================================
    # LINEAR RELATION DISCOVERY
    # ========================================================

    def fit_linear_relation(
        self,
        pairs
    ) -> Optional[Tuple[float, float]]:

        if len(pairs) < 3:
            return None

        mean_x = self.mean(
            [x for x, _ in pairs]
        )

        mean_y = self.mean(
            [y for _, y in pairs]
        )

        numerator = 0.0
        denominator = 0.0

        for x, y in pairs:

            dx = (
                x - mean_x
            )

            dy = (
                y - mean_y
            )

            numerator += (
                dx * dy
            )

            denominator += (
                dx * dx
            )

        if abs(denominator) < 1e-12:
            return None

        slope = (
            numerator
            / denominator
        )

        intercept = (
            mean_y
            - slope * mean_x
        )

        return (
            slope,
            intercept
        )

    # ========================================================
    # BUILD DISCOVERED TRANSFORMATION
    # ========================================================
    #
    # This is the central V7 step.
    #
    # AEGIS does not add "square" to a predefined zoo.
    #
    # It observes that the local rate itself has structure.
    #
    # It constructs a transformation representing that
    # relationship.
    #
    # ========================================================

    def construct_operator(self):

        rates = self.local_rates(
            self.training
        )

        if len(rates) < 4:
            return None

        relation = (
            self.fit_linear_relation(
                rates
            )
        )

        if relation is None:
            return None

        slope, intercept = relation

        # ----------------------------------------------------
        # Measure how well the discovered transformation
        # describes the observed rate.
        # ----------------------------------------------------

        predicted_rates = []

        actual_rates = []

        for x, rate in rates:

            predicted = (
                slope * x
                + intercept
            )

            predicted_rates.append(
                predicted
            )

            actual_rates.append(
                rate
            )

        rate_error = self.rmse(
            actual_rates,
            predicted_rates
        )

        # ----------------------------------------------------
        # Construct a new reusable mathematical transformation.
        # ----------------------------------------------------

        generation = (
            self.generation
        )

        name = (
            f"OP_{generation}"
        )

        expression = (
            "("
            f"{slope:.10f} * x"
            f" + "
            f"{intercept:.10f}"
            ")"
        )

        def discovered_function(
            x,
            a=slope,
            b=intercept
        ):

            return (
                a * x
                + b
            )

        return DiscoveredOperator(
            name=name,
            expression=expression,
            function=discovered_function,
            training_error=rate_error,
            generation=generation
        )

    # ========================================================
    # VALIDATE OPERATOR
    # ========================================================

    def validate_operator(
        self,
        operator
    ):

        if operator is None:
            return float("inf")

        rates = self.local_rates(
            self.validation
        )

        if not rates:
            return float("inf")

        actual = []
        predicted = []

        for x, rate in rates:

            actual.append(
                rate
            )

            predicted.append(
                operator.function(x)
            )

        error = self.rmse(
            actual,
            predicted
        )

        operator.validation_error = (
            error
        )

        return error

    # ========================================================
    # RECONSTRUCT ORIGINAL OBSERVATION
    # ========================================================
    #
    # A discovered operator is stronger if it can reconstruct
    # the original phenomenon.
    #
    # ========================================================

    def reconstruct(
        self,
        observations,
        operator
    ):

        ordered = sorted(
            observations,
            key=lambda item: item.x
        )

        if len(ordered) < 2:
            return float("inf")

        predictions = [
            ordered[0].y
        ]

        current = (
            ordered[0].y
        )

        for i in range(
            len(ordered) - 1
        ):

            x1 = (
                ordered[i].x
            )

            x2 = (
                ordered[i + 1].x
            )

            dx = (
                x2 - x1
            )

            rate = (
                operator.function(x1)
            )

            current += (
                rate * dx
            )

            predictions.append(
                current
            )

        actual = [
            item.y
            for item in ordered
        ]

        return self.rmse(
            actual,
            predictions
        )

    # ========================================================
    # PROMOTE OPERATOR
    # ========================================================

    def promote(
        self,
        operator
    ):

        if operator is None:
            return False

        if (
            operator.validation_error
            is None
        ):
            return False

        reconstruction_error = (
            self.reconstruct(
                self.validation,
                operator
            )
        )

        print()
        print(
            "[RECONSTRUCTION]"
        )

        print(
            f"Validation reconstruction RMSE: "
            f"{reconstruction_error:.8f}"
        )

        # Require both:
        #
        # 1. The operator predicts the discovered rate.
        # 2. The operator reconstructs the original phenomenon.

        if (
            operator.validation_error < 0.10
            and reconstruction_error < 0.10
        ):

            self.operators.append(
                operator
            )

            self.history.append(
                {
                    "event":
                        "OPERATOR_CREATED",
                    "name":
                        operator.name,
                    "expression":
                        operator.expression,
                    "training_error":
                        operator.training_error,
                    "validation_error":
                        operator.validation_error,
                    "reconstruction_error":
                        reconstruction_error
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
            "AEGIS v7"
        )
        print(
            "MATHEMATICAL OPERATOR EMERGENCE"
        )
        print("=" * 72)
        print()

        print(
            "[STARTING VOCABULARY]"
        )

        print(
            self.vocabulary
        )

        print()
        print(
            "[NOT SUPPLIED]"
        )

        print(
            "square"
        )

        print(
            "polynomial"
        )

        print(
            "quadratic"
        )

        print(
            "derivative"
        )

        print(
            "integration"
        )

        print()

        # ----------------------------------------------------
        # PHASE 1
        # ----------------------------------------------------

        print(
            "[PHASE 1] OBSERVATIONS"
        )

        for item in self.training:

            print(
                f"  x={item.x: .5f}"
                f"  y={item.y: .5f}"
            )

        # ----------------------------------------------------
        # PHASE 2
        # ----------------------------------------------------

        print()
        print(
            "[PHASE 2] EXTRACTING CHANGE STRUCTURE"
        )

        rates = self.local_rates(
            self.training
        )

        print(
            f"Observed transitions: "
            f"{len(rates)}"
        )

        for x, rate in rates:

            print(
                f"  x={x: .5f}"
                f"  change-rate={rate: .8f}"
            )

        # ----------------------------------------------------
        # PHASE 3
        # ----------------------------------------------------

        print()
        print(
            "[PHASE 3] CONSTRUCTING NEW OPERATOR"
        )

        self.generation += 1

        operator = (
            self.construct_operator()
        )

        if operator is None:

            print(
                "[FAILURE]"
            )

            print(
                "No mathematical operator emerged."
            )

            return

        print()
        print(
            "[DISCOVERED OPERATOR]"
        )

        print(
            "Name:",
            operator.name
        )

        print(
            "Expression:",
            operator.expression
        )

        print(
            "Generation:",
            operator.generation
        )

        print(
            "Training rate RMSE:",
            f"{operator.training_error:.8f}"
        )

        # ----------------------------------------------------
        # PHASE 4
        # ----------------------------------------------------

        print()
        print(
            "[PHASE 4] INDEPENDENT VALIDATION"
        )

        validation_error = (
            self.validate_operator(
                operator
            )
        )

        print(
            "Validation rate RMSE:",
            f"{validation_error:.8f}"
        )

        # ----------------------------------------------------
        # PHASE 5
        # ----------------------------------------------------

        print()
        print(
            "[PHASE 5] TESTING WHETHER THE"
        )

        print(
            "DISCOVERED OPERATOR RECONSTRUCTS"
        )

        print(
            "THE ORIGINAL OBSERVATION STRUCTURE"
        )

        reconstruction_training = (
            self.reconstruct(
                self.training,
                operator
            )
        )

        print(
            "Training reconstruction RMSE:",
            f"{reconstruction_training:.8f}"
        )

        # ----------------------------------------------------
        # PHASE 6
        # ----------------------------------------------------

        print()
        print(
            "[PHASE 6] PROMOTION TEST"
        )

        promoted = (
            self.promote(
                operator
            )
        )

        if promoted:

            print()
            print(
                "[PROMOTED]"
            )

            print(
                "A new mathematical operator"
            )

            print(
                "was constructed from observed"
            )

            print(
                "regularity and survived"
            )

            print(
                "independent validation."
            )

        else:

            print()
            print(
                "[REJECTED]"
            )

            print(
                "The discovered operator did not"
            )

            print(
                "meet the validation thresholds."
            )

        # ----------------------------------------------------
        # FINAL REPORT
        # ----------------------------------------------------

        print()
        print("=" * 72)

        if promoted:

            print(
                "RESULT: OPERATOR EMERGENCE DETECTED"
            )

            print()

            print(
                "Discovered:"
            )

            print(
                operator.expression
            )

            print()

            print(
                "The important transition is:"
            )

            print()

            print(
                "OBSERVATIONS"
            )

            print(
                "      ↓"
            )

            print(
                "REGULARITY"
            )

            print(
                "      ↓"
            )

            print(
                "RELATIONSHIP"
            )

            print(
                "      ↓"
            )

            print(
                "NEW OPERATOR"
            )

            print(
                "      ↓"
            )

            print(
                "INDEPENDENT VALIDATION"
            )

            print(
                "      ↓"
            )

            print(
                "REUSABLE MATHEMATICAL OBJECT"
            )

        else:

            print(
                "RESULT: NO OPERATOR PROMOTED"
            )

        print("=" * 72)
        print()


# ============================================================
# EXPERIMENT
# ============================================================

def build_experiment():

    reality = HiddenReality()

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

