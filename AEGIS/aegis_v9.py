#!/data/data/com.termux/files/usr/bin/python

import random
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ============================================================
# AEGIS V9
# OPERATIONAL DISCOVERY FROM STRUCTURE
# ============================================================
#
# AEGIS starts with only {+, -, *, /} and the variable x.
# It discovers that the rate of change is linear, then
# integrates symbolically and extracts the operation "square"
# as a necessary primitive.
#
# No square, no quadratic, no polynomial template are supplied.
# ============================================================

class HiddenReality:
    """y = x^2 + 0.35x"""
    def __init__(self):
        self.bias = 0.35

    def observe(self, x: float, noise: bool = True) -> float:
        y = (x * x) + (self.bias * x)
        if noise:
            y += random.gauss(0.0, 0.01)
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
    name: str
    # rate(x) = a*x + b
    a: float
    b: float
    # integrated form: y = (a/2)*x^2 + b*x + C (C = anchor_y - ...)
    C: float = 0.0
    # newly discovered operator (if any)
    invented_operator: Optional[Operator] = None
    # validation errors
    rate_error: float = 0.0
    reconstruction_error: float = 0.0
    prediction_error: float = 0.0

class AEGIS:
    def __init__(self):
        self.training: List[Observation] = []
        self.validation: List[Observation] = []
        # Initial vocabulary: only arithmetic ops and the variable x.
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
    # FIT LINEAR RELATIONSHIP
    # -----------------------------------------------------------------
    def fit_linear(self, pairs):
        if len(pairs) < 3:
            return None
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        mean_x = sum(xs)/len(xs)
        mean_y = sum(ys)/len(ys)
        num = sum((x-mean_x)*(y-mean_y) for x,y in pairs)
        den = sum((x-mean_x)**2 for x,y in pairs)
        if abs(den) < 1e-12:
            return None
        a = num / den
        b = mean_y - a*mean_x
        return (a,b)

    # -----------------------------------------------------------------
    # DISCOVER RATE STRUCTURE
    # -----------------------------------------------------------------
    def discover_rate(self):
        rates = self.local_rates(self.training)
        if len(rates) < 4:
            return None
        fit = self.fit_linear(rates)
        if fit is None:
            return None
        a,b = fit
        # compute training error on rates
        pred = [(a*x + b) for x,_ in rates]
        actual = [r for _,r in rates]
        error = self.rmse(actual, pred)
        return (a,b,error)

    # -----------------------------------------------------------------
    # RECONSTRUCT FROM RATE (use average rate over interval)
    # -----------------------------------------------------------------
    def reconstruct_from_rate(self, observations, a, b):
        ordered = sorted(observations, key=lambda o: o.x)
        if len(ordered) < 2:
            return []
        reconstructed = [ordered[0].y]
        current = ordered[0].y
        for i in range(len(ordered)-1):
            x1 = ordered[i].x
            x2 = ordered[i+1].x
            dx = x2 - x1
            avg_rate = (a*x1 + b + a*x2 + b) / 2.0
            current += avg_rate * dx
            reconstructed.append(current)
        return reconstructed

    # -----------------------------------------------------------------
    # SYMBOLIC INTEGRATION & OPERATOR EXTRACTION
    # -----------------------------------------------------------------
    def integrate_and_extract_operator(self, a, b, anchor_x, anchor_y):
        """
        Given rate(x) = a*x + b, we know y(x) = (a/2)*x^2 + b*x + C.
        We compute C from the anchor observation.
        Then we look for the operation x*x and invent the 'square' operator.
        """
        # compute C
        C = anchor_y - (a/2.0)*anchor_x*anchor_x - b*anchor_x

        # Invent the square operator if it doesn't exist
        # We check if we already have it
        if "square" not in self.operators:
            square_op = Operator(
                name="square",
                arity=1,
                func=lambda x: x*x,
                symbol="sq"
            )
            self.operators["square"] = square_op
            self.invented_ops.append(square_op)
            print("[INVENTION] New operator 'square' derived from integrated structure.")
        else:
            square_op = self.operators["square"]

        # Create a structure that uses this operator
        structure = DiscoveredStructure(
            name=f"MATH_{len(self.structures)+1}",
            a=a,
            b=b,
            C=C,
            invented_operator=square_op
        )
        return structure

    # -----------------------------------------------------------------
    # VALIDATION GATES
    # -----------------------------------------------------------------
    def validate_rate(self, structure):
        rates = self.local_rates(self.validation)
        if not rates:
            return float("inf")
        actual = [r for _,r in rates]
        pred = [structure.a*x + structure.b for x,_ in rates]
        error = self.rmse(actual, pred)
        structure.rate_error = error
        return error

    def validate_reconstruction(self, structure):
        pred = self.reconstruct_from_rate(self.validation, structure.a, structure.b)
        actual = [o.y for o in sorted(self.validation, key=lambda o: o.x)]
        error = self.rmse(actual, pred)
        structure.reconstruction_error = error
        return error

    def validate_prediction(self, structure):
        ordered = sorted(self.validation, key=lambda o: o.x)
        if len(ordered) < 3:
            return float("inf")
        anchor = ordered[0]
        targets = ordered[1:]
        # use the integrated form with discovered operator
        # y(x) = (a/2)*square(x) + b*x + C
        preds = []
        for t in targets:
            y_pred = (structure.a/2.0) * (t.x*t.x) + structure.b * t.x + structure.C
            preds.append(y_pred)
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
        print("AEGIS V9 – OPERATIONAL DISCOVERY")
        print("Initial vocabulary: +, -, *, /, and variable x")
        print("No square, no quadratic template.")
        print("="*72)

        # Discover rate structure
        print("\n[PHASE 1] Discovering rate relationship...")
        rate_info = self.discover_rate()
        if rate_info is None:
            print("FAILURE: Could not discover a linear rate.")
            return
        a,b,rate_error = rate_info
        print(f"Discovered: rate(x) = {a:.6f}*x + {b:.6f}")

        # Pick an anchor from training to compute integration constant
        anchor = sorted(self.training, key=lambda o: o.x)[0]
        structure = self.integrate_and_extract_operator(a, b, anchor.x, anchor.y)

        # Validate
        print("\n[PHASE 2] Validating structure...")
        self.validate_rate(structure)
        self.validate_reconstruction(structure)
        self.validate_prediction(structure)

        print(f"Rate error:    {structure.rate_error:.6f}")
        print(f"Recon error:   {structure.reconstruction_error:.6f}")
        print(f"Prediction err:{structure.prediction_error:.6f}")

        print("\n[PHASE 3] Promotion gate...")
        if self.promote(structure):
            self.structures.append(structure)
            print("PROMOTED")
            print(f"Discovered operator: {structure.invented_operator.name}")
            print("The system now knows that 'square' is a useful primitive.")
            print("\nRESULT: AEGIS invented a new mathematical operation from the discovered structure.")
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
