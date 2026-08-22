#!/data/data/com.termux/files/usr/bin/python

import random
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from collections import deque


# ============================================================
# ULTIMATE AEGIS v4
# Representation-Inventing Blind Discovery Framework
# Termux / Python Standard Library Edition
# ============================================================


# ------------------------------------------------------------
# 1. THE OPAQUE REALITY
# ------------------------------------------------------------

class HiddenReality:
    """
    AEGIS receives only numerical observations.

    The internal variables:
        _temp
        _heater
        _door
        _time

    are deliberately hidden from AEGIS.
    """

    def __init__(self):
        self._temp = 22.0
        self._heater = 0.0
        self._door = 0.0
        self._time = 0

    @staticmethod
    def _clip(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def step(self, action: List[float]) -> float:

        a0 = self._clip(
            action[0] if len(action) > 0 else 0.0,
            0.0,
            1.0
        )

        a1 = self._clip(
            action[1] if len(action) > 1 else 0.0,
            0.0,
            1.0
        )

        self._heater = a0
        self._door = a1

        # Hidden nonlinear/environmental dynamics.
        ambient = 0.2 * math.sin(self._time / 8.0)
        heat_gain = self._heater * 0.9
        heat_loss = self._door * 0.7

        self._temp += (
            heat_gain
            - heat_loss
            + ambient
            + random.gauss(0.0, 0.05)
        )

        self._temp = self._clip(
            self._temp,
            10.0,
            40.0
        )

        self._time += 1

        return round(
            self._temp + random.gauss(0.0, 0.1),
            2
        )

    def observe(self) -> float:
        return round(
            self._temp + random.gauss(0.0, 0.1),
            2
        )


# ------------------------------------------------------------
# 2. INVENTED REPRESENTATIONS
# ------------------------------------------------------------

@dataclass
class InventedVariable:
    """
    A latent variable created by AEGIS.

    No semantic human label is supplied.
    """

    id: str
    history: List[float] = field(default_factory=list)
    causal_action_index: Optional[int] = None
    causal_strength: float = 0.0


@dataclass
class InventedOperator:
    """
    A compositional mathematical operator created by AEGIS.
    """

    id: str
    expr: str
    arity: int
    func: Callable


# ------------------------------------------------------------
# 3. ULTIMATE AEGIS
# ------------------------------------------------------------

class UltimateAEGIS:

    def __init__(self):

        # ----------------------------------------------------
        # OBSERVATION SPACE
        # ----------------------------------------------------

        self.obs_history: List[float] = []
        self.action_history: List[List[float]] = []
        self.prediction_errors: List[float] = []

        # Signed residuals are preserved separately.
        self.residual_history: List[float] = []

        # ----------------------------------------------------
        # INVENTED REPRESENTATION SPACE
        # ----------------------------------------------------

        # Only the raw observable exists initially.
        self.variables: Dict[str, InventedVariable] = {
            "temp": InventedVariable(id="temp")
        }

        # Minimal initial operator vocabulary.
        self.operators: Dict[str, InventedOperator] = {

            "add": InventedOperator(
                id="add",
                expr="x+y",
                arity=2,
                func=lambda x, y: x + y
            ),

            "mul": InventedOperator(
                id="mul",
                expr="x*y",
                arity=2,
                func=lambda x, y: x * y
            ),

            "neg": InventedOperator(
                id="neg",
                expr="-x",
                arity=1,
                func=lambda x, y=None: -x
            ),
        }

        # ----------------------------------------------------
        # MODEL
        # ----------------------------------------------------

        self.model_terms: List[Dict] = []

        self._init_initial_model()

        # Persistent model failure threshold.
        self.novelty_threshold = 1.2

        # Revision memory.
        self.revision_buffer = deque(maxlen=20)

        # Number of invention cycles.
        self.invention_count = 0

    # --------------------------------------------------------
    # INITIAL MODEL
    # --------------------------------------------------------

    def _init_initial_model(self):

        self.model_terms = [

            {
                "coeff": 0.9,
                "op_id": "add",
                "var_id": "temp",
                "active": True
            },

            {
                "coeff": 0.1,
                "op_id": "add",
                "var_id": "temp",
                "active": True
            }
        ]

    # --------------------------------------------------------
    # LATENT ESTIMATION
    # --------------------------------------------------------

    def _estimate_latent(
        self,
        var: InventedVariable,
        obs: float,
        action: List[float]
    ) -> float:

        # If a causal action has been identified,
        # use that action as the latent-state driver.

        if (
            var.causal_action_index is not None
            and len(action) > var.causal_action_index
        ):
            idx = var.causal_action_index

            return (
                action[idx] * 10.0
                + obs * 0.1
            )

        # Otherwise use recent observation dynamics.
        if len(self.obs_history) > 1:

            return (
                self.obs_history[-1]
                - self.obs_history[-2]
            )

        return 0.0

    # --------------------------------------------------------
    # PREDICTION
    # --------------------------------------------------------

    def predict_next(
        self,
        last_obs: float,
        action: List[float]
    ) -> float:

        prediction = 0.0

        for term in self.model_terms:

            if not term["active"]:
                continue

            op = self.operators.get(term["op_id"])
            var = self.variables.get(term["var_id"])

            if op is None or var is None:
                continue

            # Current variable value.
            if var.id == "temp":
                value = last_obs
            else:
                value = self._estimate_latent(
                    var,
                    last_obs,
                    action
                )

            # Apply operator.
            if op.arity == 1:

                result = op.func(value)

            else:

                second = (
                    action[0]
                    if len(action) > 0
                    else 0.0
                )

                result = op.func(
                    value,
                    second
                )

            prediction += (
                term["coeff"] * result
            )

        return prediction

    # --------------------------------------------------------
    # INNER LOOP
    # --------------------------------------------------------

    def update_model(
        self,
        observed: float,
        action: List[float]
    ) -> float:

        if not self.obs_history:
            return 0.0

        last_obs = self.obs_history[-1]

        predicted = self.predict_next(
            last_obs,
            action
        )

        residual = observed - predicted
        absolute_error = abs(residual)

        self.residual_history.append(residual)
        self.prediction_errors.append(
            absolute_error
        )

        # Keep memory bounded.
        if len(self.prediction_errors) > 100:
            self.prediction_errors.pop(0)

        if len(self.residual_history) > 100:
            self.residual_history.pop(0)

        # Simple coefficient adaptation.
        denominator = abs(predicted) + 0.01

        for term in self.model_terms:

            if not term["active"]:
                continue

            adjustment = (
                0.01
                * residual
                * (observed / denominator)
            )

            term["coeff"] += adjustment

            # Prevent numerical explosion.
            term["coeff"] = max(
                -2.0,
                min(2.0, term["coeff"])
            )

        print(
            "[INNER] "
            f"Predicted={predicted:.3f} "
            f"Actual={observed:.3f} "
            f"Residual={residual:.3f} "
            f"Error={absolute_error:.3f}"
        )

        return absolute_error

    # --------------------------------------------------------
    # CORRELATION
    # --------------------------------------------------------

    @staticmethod
    def correlation(
        x: List[float],
        y: List[float]
    ) -> Optional[float]:

        if len(x) != len(y):
            return None

        if len(x) < 2:
            return None

        mean_x = sum(x) / len(x)
        mean_y = sum(y) / len(y)

        numerator = sum(
            (a - mean_x) * (b - mean_y)
            for a, b in zip(x, y)
        )

        denominator_x = math.sqrt(
            sum(
                (a - mean_x) ** 2
                for a in x
            )
        )

        denominator_y = math.sqrt(
            sum(
                (b - mean_y) ** 2
                for b in y
            )
        )

        denominator = (
            denominator_x
            * denominator_y
        )

        if denominator == 0:
            return None

        return numerator / denominator

    # --------------------------------------------------------
    # OUTER LOOP
    # REPRESENTATION INVENTION
    # --------------------------------------------------------

    def invent_if_needed(
        self,
        last_error: float,
        action: List[float],
        observed: float
    ):

        if len(self.prediction_errors) < 5:
            return

        recent = self.prediction_errors[-5:]

        mean_error = (
            sum(recent)
            / len(recent)
        )

        if mean_error < self.novelty_threshold:
            return

        print()
        print(
            "[NOVELTY] Persistent model failure."
        )
        print(
            f"[NOVELTY] Mean error={mean_error:.3f}"
        )
        print(
            "[INVENT] Searching for new representation..."
        )

        self.invention_count += 1

        # ----------------------------------------------------
        # STEP A: INVENT LATENT VARIABLE
        # ----------------------------------------------------

        if len(self.action_history) >= 5:

            window = min(
                10,
                len(self.action_history),
                len(self.residual_history)
            )

            actions = self.action_history[-window:]
            residuals = self.residual_history[-window:]

            for action_index in range(2):

                action_values = [
                    row[action_index]
                    for row in actions
                    if len(row) > action_index
                ]

                if len(action_values) != len(residuals):
                    continue

                corr = self.correlation(
                    action_values,
                    residuals
                )

                if corr is None:
                    continue

                if abs(corr) > 0.5:

                    new_id = (
                        f"z{len(self.variables)}"
                    )

                    if new_id not in self.variables:

                        self.variables[new_id] = (
                            InventedVariable(
                                id=new_id,
                                causal_action_index=action_index,
                                causal_strength=abs(corr)
                            )
                        )

                        print(
                            f"[INVENT] "
                            f"Variable={new_id} "
                            f"ActionIndex={action_index} "
                            f"Correlation={corr:.3f}"
                        )

                        self.model_terms.append(
                            {
                                "coeff": 0.1,
                                "op_id": "add",
                                "var_id": new_id,
                                "active": True
                            }
                        )

        # ----------------------------------------------------
        # STEP B: INVENT OPERATOR
        # ----------------------------------------------------

        op_list = list(
            self.operators.values()
        )

        if len(op_list) >= 2:

            op1 = random.choice(op_list)
            op2 = random.choice(op_list)

            new_id = (
                f"OP{len(self.operators)}"
            )

            # Current compositional invention:
            # square of x*y.

            if (
                op1.id == "mul"
                and op2.id == "mul"
            ):

                new_func = (
                    lambda x, y:
                    (x * y) * (x * y)
                )

                expression = (
                    "mul(mul(x,y),mul(x,y))"
                )

                if new_id not in self.operators:

                    self.operators[new_id] = (
                        InventedOperator(
                            id=new_id,
                            expr=expression,
                            arity=2,
                            func=new_func
                        )
                    )

                    print(
                        f"[INVENT] "
                        f"Operator={new_id} "
                        f"Expr={expression}"
                    )

                    self.model_terms.append(
                        {
                            "coeff": 0.05,
                            "op_id": new_id,
                            "var_id": "temp",
                            "active": True
                        }
                    )

        # Reset rolling error window.
        self.prediction_errors = []

    # --------------------------------------------------------
    # ACTION PLANNER
    # --------------------------------------------------------

    def choose_action(
        self,
        step: int
    ) -> List[float]:

        invented = [
            v
            for v in self.variables.values()
            if v.id != "temp"
        ]

        # Probe an inferred causal action.
        if invented:

            var = invented[-1]

            if var.causal_action_index is not None:

                action = [0.0, 0.0]

                index = var.causal_action_index

                action[index] = (
                    1.0
                    if step % 2 == 0
                    else 0.0
                )

                return action

        # Otherwise explore the action space.
        return [
            random.random(),
            random.random()
        ]

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    def report_state(self):

        print(
            "[ONTOLOGY] Variables:",
            list(self.variables.keys())
        )

        print(
            "[ONTOLOGY] Operators:",
            list(self.operators.keys())
        )

        active_terms = []

        for term in self.model_terms:

            if not term["active"]:
                continue

            active_terms.append(
                {
                    "coeff": round(
                        term["coeff"],
                        4
                    ),
                    "op": term["op_id"],
                    "var": term["var_id"]
                }
            )

        print(
            "[MODEL] Active terms:",
            active_terms
        )

    # --------------------------------------------------------
    # COMPLETE AEGIS LOOP
    # --------------------------------------------------------

    def run(
        self,
        reality: HiddenReality,
        max_steps: int = 30
    ):

        print()
        print("=" * 64)
        print(
            "ULTIMATE AEGIS v4"
        )
        print(
            "REPRESENTATION-INVENTING BLIND DISCOVERY"
        )
        print("=" * 64)
        print()
        print(
            "AEGIS receives numerical observations only."
        )
        print(
            "No semantic environment labels are supplied."
        )
        print()

        # ----------------------------------------------------
        # INITIAL OBSERVATION
        # ----------------------------------------------------

        observation = reality.observe()

        self.obs_history.append(
            observation
        )

        print(
            f"[OBS] Initial={observation:.3f}"
        )

        # Neutral initial action.
        action = [0.0, 0.0]

        # ----------------------------------------------------
        # MAIN LOOP
        # ----------------------------------------------------

        for step in range(max_steps):

            print()
            print(
                "-" * 64
            )
            print(
                f"STEP {step + 1}/{max_steps}"
            )
            print(
                "-" * 64
            )

            # ----------------------------------------------
            # 1. CHOOSE ACTION
            # ----------------------------------------------

            action = self.choose_action(
                step
            )

            self.action_history.append(
                action.copy()
            )

            print(
                "[ACT] Action:",
                [
                    round(x, 3)
                    for x in action
                ]
            )

            # ----------------------------------------------
            # 2. OBSERVE RESULT
            # ----------------------------------------------

            new_observation = (
                reality.step(action)
            )

            self.obs_history.append(
                new_observation
            )

            print(
                f"[OBS] {new_observation:.3f}"
            )

            # ----------------------------------------------
            # 3. FIT EXISTING MODEL
            # ----------------------------------------------

            error = self.update_model(
                new_observation,
                action
            )

            # ----------------------------------------------
            # 4. REPRESENTATION INVENTION
            # ----------------------------------------------

            self.invent_if_needed(
                error,
                action,
                new_observation
            )

            # ----------------------------------------------
            # 5. REPORT INTERNAL ONTOLOGY
            # ----------------------------------------------

            self.report_state()

            # ----------------------------------------------
            # 6. CONVERGENCE TEST
            # ----------------------------------------------

            if (
                len(self.prediction_errors) >= 5
            ):

                recent = (
                    self.prediction_errors[-5:]
                )

                average_error = (
                    sum(recent)
                    / len(recent)
                )

                if average_error < 0.3:

                    print()
                    print(
                        "[SUCCESS]"
                    )
                    print(
                        "Prediction error consistently low."
                    )
                    print(
                        "AEGIS has constructed a working"
                    )
                    print(
                        "representation for the observed dynamics."
                    )
                    print()
                    print(
                        "[IMPORTANT]"
                    )
                    print(
                        "This does NOT prove that AEGIS"
                    )
                    print(
                        "discovered the true ontology."
                    )
                    print(
                        "It proves predictive convergence."
                    )

                    return

        print()
        print("=" * 64)
        print(
            "[TERMINAL]"
        )
        print(
            "Maximum cycles exhausted."
        )
        print(
            "The system did not reach the convergence criterion."
        )
        print("=" * 64)


# ============================================================
# MAIN
# ============================================================

def main():

    random.seed(42)

    world = HiddenReality()

    agent = UltimateAEGIS()

    agent.run(
        world,
        max_steps=25
    )


if __name__ == "__main__":
    main()
